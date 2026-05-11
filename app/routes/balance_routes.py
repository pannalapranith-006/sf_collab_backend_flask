"""
Balance Routes — Real Money API
Handles all real-money (Balance) operations.

IMPORTANT: These endpoints deal with REAL financial value.
           All amounts from the client are in DOLLARS (floats).
           Internally, everything is stored as integer CENTS.

Endpoints:
  GET  /balance                        — view my balance
  GET  /balance/transactions           — transaction history
  POST /balance/deposit                — top up (Stripe webhook calls this)
  POST /balance/withdraw               — request payout
  POST /balance/pay                    — pay another user (marketplace / mentorship)

Escrow endpoints (milestone payments):
  POST /balance/escrow                 — create escrow (Founder)
  GET  /balance/escrow                 — list my escrow transactions
  GET  /balance/escrow/<id>            — get single escrow
  POST /balance/escrow/<id>/activate   — mark as active
  POST /balance/escrow/<id>/complete   — Payee: mark milestone done
  POST /balance/escrow/<id>/approve    — Payer: release funds to payee
  POST /balance/escrow/<id>/dispute    — raise a dispute
  POST /balance/escrow/<id>/cancel     — cancel and refund
  POST /balance/escrow/<id>/resolve    — Admin: resolve a dispute
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.Balance import Balance, BalanceTransaction
from app.models.EscrowTransaction import EscrowTransaction
from datetime import datetime
from sqlalchemy import desc, or_

balance_bp = Blueprint('balance', __name__)


# ============================================================================
# HELPERS
# ============================================================================

def get_or_create_balance(user_id: int) -> Balance:
    """Fetch or lazily create the balance row for a user."""
    balance = Balance.query.filter_by(user_id=user_id).first()
    if not balance:
        balance = Balance(user_id=user_id)
        db.session.add(balance)
        db.session.flush()  # get balance.id without committing
    return balance


def dollars_to_cents(dollars) -> int:
    """Convert a dollar float/int from the API body to integer cents."""
    try:
        return int(round(float(dollars) * 100))
    except (TypeError, ValueError):
        raise ValueError('Invalid amount — must be a number')


def require_admin(user_id: int):
    """Raise 403-like error if user is not admin."""
    user = User.query.get(user_id)
    if not user or not getattr(user, 'is_admin', False):
        return False
    return True


# ============================================================================
# BALANCE ENDPOINTS
# ============================================================================

@balance_bp.route('', methods=['GET'])
@jwt_required()
def get_balance():
    """Get current user's real-money balance."""
    try:
        user_id = int(get_jwt_identity())
        balance = get_or_create_balance(user_id)
        db.session.commit()  # persist if newly created
        return jsonify({'success': True, 'balance': balance.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    """Get real-money transaction history for current user."""
    try:
        user_id = int(get_jwt_identity())
        balance = get_or_create_balance(user_id)
        db.session.commit()

        page     = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        tx_type  = request.args.get('tx_type')

        query = BalanceTransaction.query.filter_by(balance_id=balance.id)
        if tx_type:
            query = query.filter_by(tx_type=tx_type)
        query = query.order_by(desc(BalanceTransaction.created_at))

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'transactions': [tx.to_dict() for tx in pagination.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            }
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/deposit', methods=['POST'])
@jwt_required()
def deposit():
    """
    Top up a user's balance.

    In production this endpoint should only be called by a verified
    Stripe webhook (verify the Stripe-Signature header before crediting).

    Body:
      amount          (float, dollars)  — e.g. 25.00
      description     (str, optional)
      stripe_payment_id (str, optional) — Stripe PaymentIntent ID
    """
    try:
        user_id = int(get_jwt_identity())
        data    = request.get_json() or {}

        cents       = dollars_to_cents(data.get('amount', 0))
        description = data.get('description', 'Deposit')
        stripe_ref  = data.get('stripe_payment_id')

        if cents <= 0:
            return jsonify({'success': False, 'error': 'Amount must be positive'}), 400

        balance = get_or_create_balance(user_id)
        tx      = balance.deposit(cents, description)
        tx.stripe_payment_id = stripe_ref

        db.session.commit()

        return jsonify({
            'success': True,
            'balance': balance.to_dict(),
            'transaction': tx.to_dict()
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/withdraw', methods=['POST'])
@jwt_required()
def withdraw():
    """
    Request a withdrawal (payout to bank).

    Body:
      amount  (float, dollars)
      description (str, optional)

    Note: In production, this should trigger a Stripe payout job,
          not immediately transfer money. The balance deduction is
          recorded here; actual bank transfer is async.
    """
    try:
        user_id = int(get_jwt_identity())
        data    = request.get_json() or {}

        cents       = dollars_to_cents(data.get('amount', 0))
        description = data.get('description', 'Withdrawal')

        if cents <= 0:
            return jsonify({'success': False, 'error': 'Amount must be positive'}), 400

        # Minimum withdrawal guard (e.g. $5.00)
        if cents < 500:
            return jsonify({'success': False,
                            'error': 'Minimum withdrawal is $5.00'}), 400

        balance = get_or_create_balance(user_id)
        tx      = balance.withdraw(cents, description)
        db.session.commit()

        # TODO: Trigger Stripe payout job via Celery task here

        return jsonify({
            'success': True,
            'balance': balance.to_dict(),
            'transaction': tx.to_dict()
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/pay', methods=['POST'])
@jwt_required()
def pay():
    """
    Direct payment to another user (marketplace / mentorship / crowdfunding).

    Body:
      recipient_id    (int)
      amount          (float, dollars)
      reference_type  (str) — 'marketplace' | 'mentorship' | 'crowdfunding'
      reference_id    (str, optional) — related entity id
      description     (str, optional)
    """
    try:
        payer_id = int(get_jwt_identity())
        data     = request.get_json() or {}

        recipient_id   = data.get('recipient_id')
        cents          = dollars_to_cents(data.get('amount', 0))
        reference_type = data.get('reference_type', 'marketplace')
        reference_id   = data.get('reference_id')
        description    = data.get('description', 'Payment')

        if not recipient_id:
            return jsonify({'success': False, 'error': 'recipient_id is required'}), 400

        recipient_id = int(recipient_id)

        if payer_id == recipient_id:
            return jsonify({'success': False, 'error': 'Cannot pay yourself'}), 400

        if cents <= 0:
            return jsonify({'success': False, 'error': 'Amount must be positive'}), 400

        # Validate recipient exists
        recipient = User.query.get(recipient_id)
        if not recipient:
            return jsonify({'success': False, 'error': 'Recipient not found'}), 404

        # Validate reference_type is a real-money use case (not crystals territory)
        allowed_types = {'marketplace', 'mentorship', 'crowdfunding', 'service', 'other'}
        if reference_type not in allowed_types:
            return jsonify({
                'success': False,
                'error': f'Invalid reference_type. Allowed: {", ".join(allowed_types)}'
            }), 400

        payer_balance     = get_or_create_balance(payer_id)
        recipient_balance = get_or_create_balance(recipient_id)

        # Deduct from payer
        payer_tx = payer_balance.pay(
            cents=cents,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description
        )
        # Credit recipient
        recipient_tx = recipient_balance.receive(
            cents=cents,
            reference_type=reference_type,
            reference_id=reference_id,
            description=f'Received: {description}'
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'payer_balance': payer_balance.to_dict(),
            'paid': cents / 100
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ESCROW ENDPOINTS
# ============================================================================

@balance_bp.route('/escrow', methods=['POST'])
@jwt_required()
def create_escrow():
    """
    Create a milestone escrow — Founder deposits funds to hold for Contributor.

    Body:
      payee_id        (int)    — contributor / mentor id
      amount          (float)  — dollars
      title           (str)    — e.g. "Phase 1 MVP"
      description     (str, optional)
      reference_type  (str)    — 'milestone' | 'freelance' | 'mentorship'
      reference_id    (str, optional) — task_id / milestone_id
      due_date        (str, optional) — ISO datetime
    """
    try:
        payer_id = int(get_jwt_identity())
        data     = request.get_json() or {}

        payee_id       = data.get('payee_id')
        cents          = dollars_to_cents(data.get('amount', 0))
        title          = data.get('title', 'Milestone Payment')
        description    = data.get('description')
        reference_type = data.get('reference_type', 'milestone')
        reference_id   = data.get('reference_id')
        due_date_str   = data.get('due_date')

        if not payee_id:
            return jsonify({'success': False, 'error': 'payee_id is required'}), 400

        payee_id = int(payee_id)

        if payer_id == payee_id:
            return jsonify({'success': False, 'error': 'Payer and payee cannot be the same'}), 400

        if cents <= 0:
            return jsonify({'success': False, 'error': 'Amount must be positive'}), 400

        # Validate payee exists
        payee = User.query.get(payee_id)
        if not payee:
            return jsonify({'success': False, 'error': 'Payee not found'}), 404

        payer_balance = get_or_create_balance(payer_id)
        payee_balance = get_or_create_balance(payee_id)
        db.session.flush()

        if payer_balance.available < cents:
            return jsonify({
                'success': False,
                'error': 'Insufficient balance',
                'available': payer_balance.available / 100,
                'required': cents / 100
            }), 400

        # Parse optional due date
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid due_date format'}), 400

        # Create escrow row
        escrow = EscrowTransaction(
            payer_id=payer_id,
            payee_id=payee_id,
            payer_balance_id=payer_balance.id,
            payee_balance_id=payee_balance.id,
            amount_cents=cents,
            title=title,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
            due_date=due_date,
        )
        db.session.add(escrow)
        db.session.flush()  # get escrow.id for the lock audit record

        # Fund it immediately (moves available → escrow_locked)
        escrow.fund()

        db.session.commit()

        return jsonify({
            'success': True,
            'escrow': escrow.to_dict(),
            'payer_balance': payer_balance.to_dict()
        }), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/escrow', methods=['GET'])
@jwt_required()
def list_escrows():
    """List escrow transactions where the current user is payer or payee."""
    try:
        user_id = int(get_jwt_identity())
        role    = request.args.get('role')  # 'payer' | 'payee' | None (both)
        status  = request.args.get('status')

        query = EscrowTransaction.query.filter(
            or_(
                EscrowTransaction.payer_id == user_id,
                EscrowTransaction.payee_id == user_id
            )
        )

        if role == 'payer':
            query = query.filter_by(payer_id=user_id)
        elif role == 'payee':
            query = query.filter_by(payee_id=user_id)

        if status:
            query = query.filter_by(status=status)

        escrows = query.order_by(desc(EscrowTransaction.created_at)).all()

        return jsonify({
            'success': True,
            'escrows': [e.to_dict() for e in escrows]
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/escrow/<int:escrow_id>', methods=['GET'])
@jwt_required()
def get_escrow(escrow_id):
    """Get a single escrow transaction."""
    try:
        user_id = int(get_jwt_identity())
        escrow  = EscrowTransaction.query.get(escrow_id)

        if not escrow:
            return jsonify({'success': False, 'error': 'Escrow not found'}), 404

        # Only payer, payee, or admin can view
        if escrow.payer_id != user_id and escrow.payee_id != user_id:
            if not require_admin(user_id):
                return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        return jsonify({'success': True, 'escrow': escrow.to_dict()}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/escrow/<int:escrow_id>/activate', methods=['POST'])
@jwt_required()
def activate_escrow(escrow_id):
    """Payer marks the escrow as active (work has started)."""
    try:
        user_id = int(get_jwt_identity())
        escrow  = EscrowTransaction.query.get(escrow_id)

        if not escrow:
            return jsonify({'success': False, 'error': 'Escrow not found'}), 404
        if escrow.payer_id != user_id:
            return jsonify({'success': False, 'error': 'Only the payer can activate this escrow'}), 403

        escrow.mark_active()
        db.session.commit()

        return jsonify({'success': True, 'escrow': escrow.to_dict()}), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/escrow/<int:escrow_id>/complete', methods=['POST'])
@jwt_required()
def complete_escrow(escrow_id):
    """Payee marks the milestone as complete — requests release."""
    try:
        user_id = int(get_jwt_identity())
        escrow  = EscrowTransaction.query.get(escrow_id)

        if not escrow:
            return jsonify({'success': False, 'error': 'Escrow not found'}), 404
        if escrow.payee_id != user_id:
            return jsonify({'success': False, 'error': 'Only the payee can mark this complete'}), 403

        escrow.request_release()
        db.session.commit()

        return jsonify({'success': True, 'escrow': escrow.to_dict()}), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/escrow/<int:escrow_id>/approve', methods=['POST'])
@jwt_required()
def approve_escrow(escrow_id):
    """Payer approves milestone — releases funds to payee."""
    try:
        user_id = int(get_jwt_identity())
        escrow  = EscrowTransaction.query.get(escrow_id)

        if not escrow:
            return jsonify({'success': False, 'error': 'Escrow not found'}), 404
        if escrow.payer_id != user_id:
            return jsonify({'success': False, 'error': 'Only the payer can approve release'}), 403

        escrow.release()
        db.session.commit()

        return jsonify({'success': True, 'escrow': escrow.to_dict()}), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/escrow/<int:escrow_id>/dispute', methods=['POST'])
@jwt_required()
def dispute_escrow(escrow_id):
    """
    Raise a dispute on an active escrow.
    Either party can dispute.
    """
    try:
        user_id = int(get_jwt_identity())
        data    = request.get_json() or {}
        escrow  = EscrowTransaction.query.get(escrow_id)

        if not escrow:
            return jsonify({'success': False, 'error': 'Escrow not found'}), 404
        if escrow.payer_id != user_id and escrow.payee_id != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        reason = data.get('reason', '')
        escrow.dispute(reason)
        db.session.commit()

        return jsonify({'success': True, 'escrow': escrow.to_dict()}), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/escrow/<int:escrow_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_escrow(escrow_id):
    """
    Cancel an escrow and refund payer.
    Only payer can cancel (before milestone is submitted).
    """
    try:
        user_id = int(get_jwt_identity())
        data    = request.get_json() or {}
        escrow  = EscrowTransaction.query.get(escrow_id)

        if not escrow:
            return jsonify({'success': False, 'error': 'Escrow not found'}), 404
        if escrow.payer_id != user_id:
            return jsonify({'success': False, 'error': 'Only the payer can cancel this escrow'}), 403
        if escrow.status in ('pending_release', 'released', 'refunded'):
            return jsonify({'success': False,
                            'error': f'Cannot cancel escrow in status: {escrow.status}'}), 400

        reason = data.get('reason', 'Cancelled by payer')
        escrow.refund(reason)
        db.session.commit()

        return jsonify({'success': True, 'escrow': escrow.to_dict()}), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@balance_bp.route('/escrow/<int:escrow_id>/resolve', methods=['POST'])
@jwt_required()
def resolve_escrow(escrow_id):
    """
    Admin resolves a disputed escrow.

    Body:
      outcome  (str) — 'release' (pay payee) | 'refund' (return to payer)
      note     (str) — resolution note
    """
    try:
        admin_id = int(get_jwt_identity())

        if not require_admin(admin_id):
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        data    = request.get_json() or {}
        escrow  = EscrowTransaction.query.get(escrow_id)

        if not escrow:
            return jsonify({'success': False, 'error': 'Escrow not found'}), 404
        if escrow.status != 'disputed':
            return jsonify({'success': False,
                            'error': f'Escrow is not in disputed state (current: {escrow.status})'}), 400

        outcome = data.get('outcome')
        note    = data.get('note', '')

        if outcome == 'release':
            escrow.resolution_note = note
            escrow.resolved_by     = admin_id
            escrow.release()
        elif outcome == 'refund':
            escrow.resolved_by = admin_id
            escrow.refund(reason=note or 'Admin: refund after dispute')
        else:
            return jsonify({'success': False,
                            'error': 'outcome must be "release" or "refund"'}), 400

        db.session.commit()

        return jsonify({'success': True, 'escrow': escrow.to_dict()}), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500