"""
Payment Routes with Notification Triggers
SF Collab Notification System - Section 4.7 Rewards & Payments
"""
import stripe
from flask import Blueprint, request, jsonify, current_app, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_cors import cross_origin
from app.models.transaction import Transaction
from app.extensions import db, celery
from app.models.plan import Plan
from app.subscription_plans import PLANS
from app.models.user import User
from app.utils.helper import success_response, error_response, paginate
# Import notification helpers
from app.notifications.helpers import (
    notify_payment_sent,
    notify_payment_received,
    notify_points_earned,
    notify_contribution_verified
)
# Real-money Balance model — deposits from Stripe land here
from app.models.Balance import Balance, BalanceTransaction
# Crystal visibility boosts — needed for the expiry Celery task
from app.models.Crystal import VisibilityBoost
from datetime import datetime

payment_bp = Blueprint("payments", __name__, url_prefix="/payments")


# =============================================================================
# CELERY TASK — Auto-expire Visibility Boosts
# =============================================================================
# Runs every 10 minutes (configured in extensions.py beat_schedule).
# Finds all boosts whose expires_at has passed and marks them inactive.
# This keeps the discovery/ranking system accurate without manual cleanup.
# =============================================================================
# @celery.task(name="app.routes.payment_routes.expire_visibility_boosts")
def expire_visibility_boosts():
    """
    Background task: mark expired VisibilityBoosts as inactive.
    Scheduled via Celery Beat every 10 minutes.

    To run manually (for testing):
        from app.routes.payment_routes import expire_visibility_boosts
        expire_visibility_boosts.delay()
    """
    now = datetime.utcnow()
    expired = VisibilityBoost.query.filter(
        VisibilityBoost.is_active == True,
        VisibilityBoost.expires_at <= now
    ).all()

    count = len(expired)
    for boost in expired:
        boost.is_active = False

    if count > 0:
        db.session.commit()
        print(f"[Celery] Expired {count} visibility boost(s)")

    return {"expired_count": count}


def get_user_full_name(user_id):
    """Helper to get user's full name"""
    user = User.query.get(user_id)
    if user:
        return f"{user.first_name or ''} {user.last_name or ''}".strip() or "Someone"
    return "Someone"


def format_amount(amount_cents, currency='usd'):
    """Format amount from cents to readable string"""
    amount = amount_cents / 100
    if currency.upper() == 'USD':
        return f"${amount:.2f}"
    return f"{amount:.2f} {currency.upper()}"


@payment_bp.route("/plans", methods=["GET"])
@cross_origin()
def get_plans():
    plans = PLANS

    type = request.args.get("type")
    if type:
        plans = list(filter(lambda p: p.get('category') == type, PLANS))
    return jsonify([{
            "title": plan['category'],
            "currency": plan.get('currency', 'usd'),
            "description": plan.get('description', ''),
            "data": plan.get('data', []),
            "roles": plan.get('roles', []),
        } for plan in plans])


@payment_bp.route("/plans/<plan_id>", methods=["GET"])
def get_plan_by_id(plan_id):
    # Loop over all categories
    for category in PLANS:
        # 1️⃣ Check roles -> tiers (crowdfunding, standard)
        if 'roles' in category:
            for role in category['roles']:
                for tier in role.get('tiers', []):
                    if tier.get('id') == plan_id:
                        result = tier.copy()
                        result['category'] = category.get('category')
                        result['role'] = role.get('role')
                        return jsonify(result)

        # 2️⃣ Check ai-tools -> tools
        if 'ai-tools' in category:
            for tool in category['tools']:
                if tool.get('id') == plan_id:
                    result = tool.copy()
                    result['category'] = category.get('category')
                    return jsonify(result)

        # 3️⃣ Check extras -> extras -> items
        if 'extras' in category:
            for extra_group in category['extras']:
                for item in extra_group.get('items', []):
                    if item.get('id') == plan_id:
                        result = item.copy()
                        result['category'] = category.get('category')
                        result['extra_group'] = extra_group.get('title')
                        return jsonify(result)

        # 4️⃣ Check credits -> credit_packs
        if 'credit_packs' in category:
            for pack in category['credit_packs']:
                if pack.get('id') == plan_id:
                    result = pack.copy()
                    result['category'] = category.get('category')
                    return jsonify(result)

        # 5️⃣ Check credits -> topups
        if 'topups' in category:
            for topup in category['topups']:
                if topup.get('id') == plan_id:
                    result = topup.copy()
                    result['category'] = category.get('category')
                    return jsonify(result)

    # Not found
    return jsonify({"error": "Plan not found"}), 404


@payment_bp.route("create-payment-intent", methods=["POST"])
@jwt_required()
def create_payment_intent():
    data = request.get_json()
    price_id = data.get("priceId")
    
    plan = next((plan for plan in PLANS if plan['stripe_price_id'] == price_id), None)
    if not plan:
        return jsonify({"error": "Invalid price ID"}), 400

    intent = stripe.PaymentIntent.create(
        amount=plan['price'],
        currency=plan['currency'],
        metadata={
            "integration_check": "accept_a_payment",
            "user_id": get_jwt_identity(),
            "plan_id": plan['id']
            },
        return_url=current_app.config['FRONTEND_URL'] + '/checkout/success',
        confirm=True
    )

    return jsonify({
        "clientSecret": intent.client_secret
    }), 200


@payment_bp.route('/create-checkout-session', methods=['POST'])
def checkout():
    try:
        data = request.get_json()
        currency = data.get('currency', 'usd')
        tier_id = data.get('id')
        user_id = data.get('user_id')
        product = data.get('title')
        amount = data.get('price')  # amount in cents
        description = data.get('description', '')
        type = data.get('type', 'subscription')
        option = data.get('option', None)

        session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price_data": {
                    "currency": currency,
                    "product_data": {"name": product},
                    "unit_amount": amount,
                },
                "quantity": 1,
                },
            ],
            mode="payment",
            ui_mode="hosted",
            metadata={
                "user_id": user_id,
                "plan_id": tier_id,
                "option": str(option) if option else "",
                "type": type
            },
            # The URL of your payment completion page
            success_url=f"{current_app.config['FRONTEND_URL']}/checkout/return?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{current_app.config['FRONTEND_URL']}/checkout/cancel",
        )
        return jsonify({
            'checkoutSessionClientSecret': session['client_secret'],
            'url': session['url'],
            'success': True
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@payment_bp.route("/checkout-session/<session_id>", methods=["GET"])
def get_checkout_session(session_id):
    session = stripe.checkout.Session.retrieve(session_id)
    return jsonify(session)


# ─────────────────────────────────────────────────────────────────
# CROWDFUNDING INTEREST ENDPOINT
# Crowdfunding payments are disabled. This endpoint logs user interest
# so we can notify them when crowdfunding launches.
# No payment is created. No campaign is started.
# ─────────────────────────────────────────────────────────────────
@payment_bp.route("/crowdfunding-interest", methods=["POST"])
@jwt_required()
def register_crowdfunding_interest():
    """
    Log that the current user is interested in crowdfunding.
    Stores interest in the database (user metadata).
    Returns 409 if already registered, 200 on success.
    """
    try:
        current_user_id = int(get_jwt_identity())
        user = User.query.get(current_user_id)

        if not user:
            return error_response("User not found", 404)

        # Read existing preferences safely
        preferences = {}
        if hasattr(user, 'preferences') and isinstance(user.preferences, dict):
            preferences = dict(user.preferences)

        if preferences.get("crowdfunding_interest"):
            return jsonify({
                "success": True,
                "already_registered": True,
                "message": "You have already registered your interest in crowdfunding."
            }), 409

        # Mark interest with a proper datetime string
        preferences["crowdfunding_interest"] = True
        preferences["crowdfunding_interest_at"] = datetime.utcnow().isoformat()

        # Use update_preferences if available, otherwise set directly
        if hasattr(user, 'update_preferences'):
            user.update_preferences(preferences)
        else:
            user.preferences = preferences

        db.session.commit()

        # Optionally send a confirmation notification
        try:
            from app.notifications.helpers import notify_general
            notify_general(
                user_id=current_user_id,
                title="Crowdfunding Interest Registered 🚀",
                message="Thanks for your interest! We'll notify you the moment crowdfunding goes live.",
                notification_type="system"
            )
        except Exception:
            pass  # Non-critical — don't fail the request

        return success_response(
            {"registered": True},
            "Your interest in crowdfunding has been registered! We'll notify you when it launches.",
            200
        )

    except Exception as e:
        db.session.rollback()
        return error_response(f"Failed to register interest: {str(e)}", 500)


# @payment_bp.route("/record-transaction", methods=["POST"])
# @jwt_required()
# def record_transaction():
#     try:
#         data = request.get_json()
#         user_id = data.get("user_id")
#         plan_id = data.get("plan_id")
#         amount = data.get("amount")
#         currency = data.get("currency")
#         type = data.get("type", "subscription")

#         if type not in ["subscription", "donation"]:
#             return jsonify({"error": "Invalid transaction type"}), 400
        
#         if type == "subscription":
#             stripe_payment_intent_id = data.get("stripe_payment_intent_id")
#             if not all([user_id, plan_id, amount, currency, stripe_payment_intent_id]):
#                 return jsonify({"error": "Missing required fields"}), 400
#             existing_tx = Transaction.query.filter_by(stripe_payment_intent_id=stripe_payment_intent_id).first()
#             if existing_tx:
#                 return jsonify({"error": "Transaction already recorded"}), 400
#             transaction = Transaction(
#                 user_id=user_id,
#                 plan_id=plan_id,
#                 amount=amount,
#                 currency=currency,
#                 stripe_payment_intent_id=stripe_payment_intent_id,
#                 status="completed"
#             )

#             # Update user's plan here if needed
#             user = User.query.get(user_id)
#             if user:
#                 user.plan_id = plan_id
#             db.session.add(transaction)
            
#         elif type == "donation":
#             stripe_checkout_session_id = data.get("stripe_checkout_session_id")
#             if not all([user_id, amount, currency, stripe_checkout_session_id]):
#                 return jsonify({"error": "Missing required fields for donation"}), 400
#             existing_tx = Transaction.query.filter_by(stripe_checkout_session_id=stripe_checkout_session_id).first()
#             if existing_tx:
#                 return jsonify({"error": "Donation transaction already recorded"}), 400
#             transaction = Transaction(
#                 user_id=user_id,
#                 amount=amount,
#                 currency=currency,
#                 stripe_checkout_session_id=stripe_checkout_session_id,
#                 status="completed",
#                 type="donation"
#             )
#             db.session.add(transaction)
        
#         db.session.commit()
        
#         # ════════════════════════════════════════════════════════════
#         # ✨ NOTIFICATION: Payment Sent/Received (4.7)
#         # ════════════════════════════════════════════════════════════
#         try:
#             amount_str = format_amount(amount, currency)
            
#             # Notify user their payment was processed
#             notify_payment_sent(
#                 user_id=user_id,
#                 amount=amount_str,
#                 recipient="SF Collab",
#                 payment_id=transaction.id
#             )
            
#             # If donation, also notify as contribution
#             if type == "donation":
#                 notify_contribution_verified(
#                     user_id=user_id,
#                     project="SF Collab Platform",
#                     contribution_id=transaction.id
#                 )
#         except Exception as e:
#             print(f"⚠️ Payment notification failed: {e}")
        
#         return jsonify({
#             "success": True,
#             "message": "Transaction recorded successfully",
#             "transaction_id": transaction.id
#         }), 201
#     except Exception as e:
#         db.session.rollback()
#         return jsonify({"error": str(e)}), 500


@payment_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    endpoint_secret = current_app.config["STRIPE_WEBHOOK_SECRET"]

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        print(f"✅ [WEBHOOK] Event verified: {event['type']}")
    except Exception as e:
        print(f"❌ [WEBHOOK] Signature verification failed: {e}")
        return "", 400

    # ==========================================================
    # ONLY process checkout.session.completed
    # ==========================================================
    if event["type"] != "checkout.session.completed":
        print(f"ℹ️ [WEBHOOK] Ignored event: {event['type']}")
        return "", 200

    try:
        session = event["data"]["object"]
        metadata = session.get("metadata") or {}

        print("📦 [WEBHOOK] Checkout Session received")
        print("📦 [WEBHOOK] Session ID:", session.get("id"))
        print("📦 [WEBHOOK] Metadata:", metadata)

        # ======================================================
        # Extract metadata (DEFENSIVE)
        # ======================================================
        raw_user_id = metadata.get("user_id")
        raw_plan_id = metadata.get("plan_id")

        user_id = int(raw_user_id) if raw_user_id and str(raw_user_id).isdigit() else None
        plan_id = raw_plan_id if raw_plan_id else None

        tx_type = metadata.get("type") or "subscription"
        donation_message = metadata.get("message") or ""

        amount = session.get("amount_total") or 0
        currency = session.get("currency") or "usd"

        print(f"👤 User ID: {user_id}")
        print(f"🧾 Type: {tx_type}")
        print(f"💰 Amount: {amount} {currency}")

        # ======================================================
        # Idempotency check
        # ======================================================
        existing_tx = Transaction.query.filter_by(
            stripe_checkout_session_id=session.get("id")
        ).first()

        if existing_tx:
            print(f"⚠️ [WEBHOOK] Transaction already exists (ID {existing_tx.id})")
            return "", 200

        # ======================================================
        # Create transaction
        # ======================================================
        tx = Transaction(
            user_id=user_id,
            plan_id=plan_id,
            amount=amount,
            currency=currency,
            stripe_checkout_session_id=session.get("id"),
            status="completed",
            type=tx_type,
            donation_message=donation_message
        )

        db.session.add(tx)

        # ======================================================
        # Update user plan if needed
        # ======================================================
        if user_id and tx_type in ("subscription", "crowdfunding") and plan_id:
            user = User.query.get(user_id)
            if user:
                user.plan_id = plan_id

                plan_credits = 0
                CREDITS = {
                    "crowdfunding-founder-explorer": 1000,
                    "crowdfunding-founder-starter-supporter": 1000,
                    "crowdfunding-founder-pro": 2500,
                    "crowdfunding-founder-power": 7000,
                    "crowdfunding-founder-champion": 7000,
                    "crowdfunding-founder-patron": 7000,
                    "crowdfunding-founding-partner": 10000,
                    "crowdfunding-strategic-supporter": 10000,
                    "crowdfunding-builder-supporter": 0,
                    "crowdfunding-builder-early": 0,
                    "crowdfunding-builder-starter": 0,
                    "crowdfunding-builder-pro-supporter": 0,
                    "crowdfunding-builder-power-supporter": 0,
                    "crowdfunding-builder-champion": 0,
                    "crowdfunding-builder-patron": 0,
                    "founder-starter": 1000,
                    "founder-pro": 5000,
                    "founder-scale": 10000,
                    "founder-partner": 25000,
                    "builder-pro": 0,
                    "builder-plus": 0,
                    "builder-elite": 0,
                    "credits-monthly-1000": 1000,
                    "credits-monthly-3000": 3000,
                    "credits-monthly-7000": 7000,
                    "credits-monthly-16000": 16000,
                    "credits-topup-500": 500,
                    "credits-topup-1500": 1500,
                    "credits-topup-5000": 5000,
                    "credits-topup-15000": 15000,
                }
                plan_credits = CREDITS.get(plan_id, 0)
                
                if plan_credits > 0:
                    # Keep User.credits in sync for backward compatibility
                    user.credits = (user.credits or 0) + plan_credits
                    
                    # Primary source of truth: UserWallet.credits
                    if not user.wallet:
                        from app.models.UserWallet import UserWallet
                        user.wallet = UserWallet(user_id=user.id)
                        db.session.add(user.wallet)
                        db.session.flush()
                        
                    user.wallet.add_credits(
                        amount=plan_credits,
                        description=f"Purchased plan/top-up: {plan_id}"
                    )
            else:
                print(f"⚠️ User {user_id} not found")

        # ======================================================
        # Deposit type → credit the real-money Balance model
        # This is separate from AI credits (UserWallet.credits).
        # Balance is the financial settlement layer used for
        # marketplace purchases, mentorship, and crowdfunding.
        # ======================================================
        if user_id and tx_type == "deposit":
            user = User.query.get(user_id)
            if user:
                balance = Balance.query.filter_by(user_id=user_id).first()
                if not balance:
                    balance = Balance(user_id=user_id)
                    db.session.add(balance)
                    db.session.flush()

                balance_tx = balance.deposit(
                    cents=amount,
                    description=f"Stripe deposit — session {session.get('id')}"
                )
                balance_tx.stripe_payment_id = session.get("id")
                print(f"✅ [WEBHOOK] Credited Balance: {amount}¢ for user {user_id}")
            else:
                print(f"⚠️ [WEBHOOK] Deposit: user {user_id} not found")

        db.session.commit()
        print(f"✅ [WEBHOOK] Transaction stored (ID {tx.id})")

        # ======================================================
        # Notifications (NON-BLOCKING)
        # ======================================================
        try:
            if user_id:
                amount_str = format_amount(amount, currency)

                notify_payment_sent(
                    user_id=user_id,
                    amount=amount_str,
                    recipient="SF Collab",
                    payment_id=tx.id,
                    transaction=tx
                )

                # if tx_type == "donation":
                #     notify_points_earned(
                #         user_id=user_id,
                #         points=amount,
                #         reason="Donation to SF Collab"
                #     )

                # elif tx_type == "crowdfunding":
                #     notify_points_earned(
                #         user_id=user_id,
                #         points=amount,
                #         reason="Crowdfunding contribution"
                #     )

        except Exception as e:
            print(f"❌ [WEBHOOK] Notification error (ignored): {e}")

    except Exception as e:
        # ======================================================
        # ABSOLUTE SAFETY NET (NO STRIPE RETRIES)
        # ======================================================
        import traceback
        import re
        traceback.print_exc()
        db.session.rollback()
        print(f"❌ [WEBHOOK] Fatal processing error: {e}")

        # IMPORTANT: still return 200 so Stripe stops retrying
        return "", 200

    print("🎉 [WEBHOOK] Processing complete")
    return "", 200



@payment_bp.route("/create-donation-session", methods=["POST", "OPTIONS"])
@jwt_required()
def create_donation_session():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    data = request.get_json()
    amount = data.get("amount")
    user_id = get_jwt_identity()
    email = data.get("email")
    name = data.get("name")
    message = data.get("message", "")
    if not all([amount, user_id, email]):
        return jsonify({"error": "Missing required fields"}), 400
    
    session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price_data": {
                    "currency": 'usd',
                    "product_data": {"name": 'Donation'},
                    "unit_amount": amount,
                },
                "quantity": 1,
                },
            ],
            mode="payment",
            ui_mode="hosted",
            metadata={
                "user_id": user_id,
                "message": message,
                "name": name,
                "type": "donation"
            },
            success_url=f"{current_app.config['FRONTEND_URL']}/checkout/return?session_id={{CHECKOUT_SESSION_ID}}&donation=true",
            cancel_url=f"{current_app.config['FRONTEND_URL']}/donate",
        )
    return jsonify({
        'checkoutSessionClientSecret': session['client_secret'],
        'url': session['url'],
        'success': True
    })


@payment_bp.route("/total-donations", methods=["GET"])
@jwt_required()
def get_total_donations():
    total = db.session.query(db.func.sum(Transaction.amount)).filter_by(type="donation", status="completed").scalar()
    return success_response({"total_donations": total or 0})


@payment_bp.route("/donations", methods=["GET"])
@jwt_required()
def get_donations():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = Transaction.query.filter_by(type="donation", status="completed")
    total_donations = 0
    for donation in query.all():
        total_donations += donation.amount
    paginated = paginate(query, page=page, per_page=per_page)
    
    result = []

    for donation in paginated['items']:
        user = User.query.get(donation.user_id)
        result.append({
            "id": donation.id,
            "user": {
                "id": user.id,
                "firstName": user.first_name,
                "lastName": user.last_name,
                "email": user.email
            } if user else None,
            "message": donation.donation_message,
            "amount": donation.amount,
            "currency": donation.currency,
            "createdAt": donation.created_at.isoformat()
        })
    
    return success_response({
        "donations": result,
        "pagination": {
            "page": paginated['page'],
            "per_page": paginated['per_page'],
            "total_donations": total_donations,
            "total": paginated['total'],
            "pages": paginated['pages']
        }
    })


@payment_bp.route("/total-crowdfunding", methods=["GET"])
@jwt_required()
def get_total_crowdfunding():
    total = db.session.query(db.func.sum(Transaction.amount)).filter_by(type="crowdfunding", status="completed").scalar()
    return success_response({"total_crowdfunding": total or 0})


@payment_bp.route("/crowdfunding", methods=["GET"])
@jwt_required()
def get_crowdfunding_transactions():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = Transaction.query.filter_by(type="crowdfunding", status="completed")
    print("QUERY:", list(map(lambda x: x.to_dict(), query.all())))
    total_crowd = 0
    for tx in query.all():
        total_crowd += tx.amount
    paginated = paginate(query, page=page, per_page=per_page)
    
    result = []
    for tx in paginated['items']:
        user = User.query.get(tx.user_id)
        result.append({
            "id": tx.id,
            "user": {
                "id": user.id,
                "firstName": user.first_name,
                "lastName": user.last_name,
                "email": user.email
            } if user else None,
            "amount": tx.amount,
            "planId": tx.plan_id,
            "currency": tx.currency,
            "createdAt": tx.created_at.isoformat()
        })
    return success_response({
        "crowdfunding_transactions": result,
        "pagination": {
            "page": paginated['page'],
            "per_page": paginated['per_page'],
            "total_crowdfunding": total_crowd,
            "total": paginated['total'],
            "pages": paginated['pages']
        }
    })


@payment_bp.route("/credits", methods=["GET"])
@jwt_required()
def get_credits():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return error_response("User not found", 404)
    wallet_credits = user.wallet.credits if user.wallet else user.credits or 0
    return success_response({"credits": wallet_credits})

@payment_bp.route("/ai-tools", methods=["GET"])
@jwt_required()
def get_ai_tools():
    ai_plans = [plan for plan in PLANS if plan['category'] == 'ai-tools']
    if not ai_plans:
        return success_response({"tools": []})
    tools = ai_plans[0].get('tools', [])
    return success_response({"tools": tools})

@payment_bp.route("/deposit", methods=["POST"])
@jwt_required()
def deposit_funds():
    """Allow users to deposit real money into their platform wallet"""
    try:
        data = request.get_json()
        amount = data.get("amount")  # in cents
        user_id = get_jwt_identity()
        
        if not amount or amount <= 0:
            return error_response("Invalid amount", 400)
        
        user = User.query.get(user_id)
        if not user:
            return error_response("User not found", 404)
        
        session = stripe.checkout.Session.create(
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Platform Wallet Deposit"},
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            mode="payment",
            ui_mode="hosted",
            metadata={
                "user_id": user_id,
                "type": "deposit",
            },
            success_url=f"{current_app.config['FRONTEND_URL']}/wallet/deposit/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{current_app.config['FRONTEND_URL']}/wallet/deposit/cancel",
        )
        
        return jsonify({
            "checkoutSessionClientSecret": session["client_secret"],
            "url": session["url"],
            "success": True
        })
    except Exception as e:
        return error_response(str(e), 500)
@payment_bp.route("/wallet-balance", methods=["GET"])
@jwt_required()
def get_wallet_balance():
    """Get user's wallet balance (balance is separate from credits)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return error_response("User not found", 404)
        
        balance = user.wallet.credits if user.wallet else 0
        
        return success_response({
            "balance": balance,
            "currency": "usd"
        })
    except Exception as e:
        return error_response(str(e), 500)
@payment_bp.route("/withdraw", methods=["POST"])
@jwt_required()
def withdraw_funds():
    """Withdraw funds from wallet to connected bank account"""
    try:
        data = request.get_json()
        amount = data.get("amount")  # in cents
        user_id = get_jwt_identity()
        
        if not amount or amount <= 0:
            return error_response("Invalid amount", 400)
        
        user = User.query.get(user_id)
        if not user:
            return error_response("User not found", 404)
        
        current_balance = user.wallet.credits if user.wallet else 0
        if current_balance < amount:
            return error_response("Insufficient balance", 400)
        
        if not user.stripe_connect_account_id:
            return error_response("No connected bank account. Please connect Stripe account first.", 400)
        
        # Create payout to connected account
        payout = stripe.Payout.create(
            amount=amount,
            currency="usd",
            destination=user.stripe_connect_account_id,
        )
        
        # Deduct from wallet using the model method
        user.wallet.spend_credits(amount, description="Withdrawal to bank account")
        
        # Create withdrawal transaction record
        withdrawal_tx = Transaction(
            user_id=user_id,
            amount=amount,
            currency="usd",
            type="withdrawal",
            status="completed",
            stripe_payout_id=payout.id
        )
        
        db.session.add(withdrawal_tx)
        db.session.commit()
        
        return success_response({
            "withdrawal_id": withdrawal_tx.id,
            "amount": amount,
            "new_balance": user.wallet.credits,
            "payout_id": payout.id
        }, "Withdrawal processed successfully", 200)
    except Exception as e:
        db.session.rollback()
        return error_response(str(e), 500)
@payment_bp.route("/wallet-transactions", methods=["GET"])
@jwt_required()
def get_wallet_transactions():
    """Get user's wallet transaction history"""
    try:
        user_id = get_jwt_identity()
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        
        query = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.type.in_(["deposit", "withdrawal"])
        ).order_by(Transaction.created_at.desc())
        
        paginated = paginate(query, page=page, per_page=per_page)
        
        result = [
            {
                "id": tx.id,
                "type": tx.type,
                "amount": tx.amount,
                "status": tx.status,
                "createdAt": tx.created_at.isoformat()
            }
            for tx in paginated["items"]
        ]
        
        return success_response({
            "transactions": result,
            "pagination": paginated
        })
    except Exception as e:
        return error_response(str(e), 500)
