"""
Crystal Routes — Visibility Acceleration API
IMPORTANT PLATFORM RULE:
  Crystals CANNOT be used for payments.
  Crystals are ONLY for temporary visibility/discovery acceleration.

Endpoints:
  GET  /crystals                          — my crystal wallet
  GET  /crystals/transactions             — crystal transaction history
  GET  /crystals/boosts                   — my active/past boosts
  POST /crystals/boost                    — apply a visibility boost (spend crystals)
  POST /crystals/admin/grant              — Admin: grant crystals to a user
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.Crystal import (
    CrystalWallet, CrystalTransaction, VisibilityBoost,
    CRYSTAL_SPEND_TYPES
)
from datetime import datetime, timedelta
from sqlalchemy import desc

crystals_bp = Blueprint('crystals', __name__)


# ============================================================================
# HELPERS
# ============================================================================

def get_or_create_crystal_wallet(user_id: int) -> CrystalWallet:
    """Fetch or lazily create the crystal wallet for a user."""
    wallet = CrystalWallet.query.filter_by(user_id=user_id).first()
    if not wallet:
        wallet = CrystalWallet(user_id=user_id)
        db.session.add(wallet)
        db.session.flush()
    return wallet


def require_admin(user_id: int) -> bool:
    user = User.query.get(user_id)
    return bool(user and getattr(user, 'is_admin', False))


# Pricing table (crystals per boost type per 24h block)
BOOST_PRICING = {
    'visibility_boost':   50,    # general profile discovery — 50 crystals / 24h
    'listing_promotion':  100,   # promote a startup listing — 100 crystals / 24h
    'launch_promotion':   200,   # front-page launch slot — 200 crystals / 24h
    'mentor_priority':    75,    # matchmaking queue boost — 75 crystals / 24h
    'project_boost':      80,    # project discovery boost — 80 crystals / 24h
}

BOOST_DURATION_HOURS = 24  # All boosts last 24 hours per unit purchased


# ============================================================================
# CRYSTAL WALLET ENDPOINTS
# ============================================================================

@crystals_bp.route('', methods=['GET'])
@jwt_required()
def get_crystal_wallet():
    """Get current user's crystal wallet."""
    try:
        user_id = int(get_jwt_identity())
        wallet  = get_or_create_crystal_wallet(user_id)
        db.session.commit()
        return jsonify({'success': True, 'crystal_wallet': wallet.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@crystals_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_crystal_transactions():
    """Get crystal transaction history."""
    try:
        user_id  = int(get_jwt_identity())
        wallet   = get_or_create_crystal_wallet(user_id)
        db.session.commit()

        page      = request.args.get('page', 1, type=int)
        per_page  = min(request.args.get('per_page', 20, type=int), 100)
        direction = request.args.get('direction')  # 'credit' | 'debit'

        query = CrystalTransaction.query.filter_by(crystal_wallet_id=wallet.id)
        if direction in ('credit', 'debit'):
            query = query.filter_by(direction=direction)
        query = query.order_by(desc(CrystalTransaction.created_at))

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


@crystals_bp.route('/boosts', methods=['GET'])
@jwt_required()
def get_boosts():
    """Get current user's visibility boosts (active and past)."""
    try:
        user_id      = int(get_jwt_identity())
        active_only  = request.args.get('active_only', 'false').lower() == 'true'

        query = VisibilityBoost.query.filter_by(user_id=user_id)
        if active_only:
            now   = datetime.utcnow()
            query = query.filter(
                VisibilityBoost.is_active == True,
                VisibilityBoost.expires_at > now
            )
        query = query.order_by(desc(VisibilityBoost.created_at))
        boosts = query.all()

        return jsonify({
            'success': True,
            'boosts': [b.to_dict() for b in boosts]
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@crystals_bp.route('/pricing', methods=['GET'])
@jwt_required()
def get_pricing():
    """Get the crystal cost for each boost type."""
    return jsonify({
        'success': True,
        'pricing': BOOST_PRICING,
        'duration_hours': BOOST_DURATION_HOURS,
        'note': (
            'Crystals are for visibility acceleration only. '
            'They cannot be used for payments or marketplace purchases.'
        )
    }), 200


# ============================================================================
# BOOST ENDPOINT
# ============================================================================

@crystals_bp.route('/boost', methods=['POST'])
@jwt_required()
def apply_boost():
    """
    Apply a visibility boost by spending Crystals.

    RULE: Crystals ONLY accelerate discovery — NOT payments.

    Body:
      boost_type   (str) — one of CRYSTAL_SPEND_TYPES
      target_type  (str, optional) — 'startup' | 'project' | 'profile'
      target_id    (str, optional) — the id of the entity being boosted
      duration_units (int, optional) — number of 24h blocks (default: 1)
    """
    try:
        user_id = int(get_jwt_identity())
        data    = request.get_json() or {}

        boost_type     = data.get('boost_type')
        target_type    = data.get('target_type', 'profile')
        target_id      = data.get('target_id', str(user_id))
        duration_units = max(1, int(data.get('duration_units', 1)))

        if not boost_type:
            return jsonify({'success': False, 'error': 'boost_type is required'}), 400

        if boost_type not in CRYSTAL_SPEND_TYPES:
            return jsonify({
                'success': False,
                'error': (
                    f'Invalid boost_type "{boost_type}". '
                    f'Allowed: {", ".join(sorted(CRYSTAL_SPEND_TYPES))}'
                )
            }), 400

        # Calculate cost
        cost_per_unit = BOOST_PRICING.get(boost_type, 50)
        total_cost    = cost_per_unit * duration_units

        wallet = get_or_create_crystal_wallet(user_id)
        db.session.flush()

        if wallet.balance < total_cost:
            return jsonify({
                'success': False,
                'error': 'Insufficient crystals',
                'balance': wallet.balance,
                'required': total_cost
            }), 400

        # Spend crystals
        description = (
            f'{boost_type.replace("_", " ").title()} boost '
            f'({duration_units} × {BOOST_DURATION_HOURS}h)'
        )
        tx = wallet.spend_crystals(
            amount=total_cost,
            usage_type=boost_type,
            description=description,
            reference_id=target_id,
        )

        # Create boost record
        now        = datetime.utcnow()
        expires_at = now + timedelta(hours=BOOST_DURATION_HOURS * duration_units)

        boost = VisibilityBoost(
            user_id=user_id,
            crystal_wallet_id=wallet.id,
            boost_type=boost_type,
            crystals_spent=total_cost,
            target_type=target_type,
            target_id=target_id,
            duration_hours=BOOST_DURATION_HOURS * duration_units,
            started_at=now,
            expires_at=expires_at,
            is_active=True,
        )
        db.session.add(boost)
        db.session.commit()

        return jsonify({
            'success': True,
            'boost': boost.to_dict(),
            'crystal_wallet': wallet.to_dict(),
            'crystals_spent': total_cost,
            'expires_at': expires_at.isoformat(),
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@crystals_bp.route('/admin/grant', methods=['POST'])
@jwt_required()
def admin_grant_crystals():
    """
    Admin: grant crystals to a user (e.g. for events, promotions).

    Body:
      user_id      (int)
      amount       (int)
      usage_type   (str) — 'admin_grant' | 'event_reward'
      description  (str, optional)
    """
    try:
        admin_id = int(get_jwt_identity())

        if not require_admin(admin_id):
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        data       = request.get_json() or {}
        user_id    = data.get('user_id')
        amount     = int(data.get('amount', 0))
        usage_type = data.get('usage_type', 'admin_grant')
        description= data.get('description', 'Admin crystal grant')

        if not user_id:
            return jsonify({'success': False, 'error': 'user_id is required'}), 400

        user_id = int(user_id)

        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be positive'}), 400

        if usage_type not in ('admin_grant', 'event_reward'):
            return jsonify({
                'success': False,
                'error': 'usage_type must be "admin_grant" or "event_reward"'
            }), 400

        target_user = User.query.get(user_id)
        if not target_user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        wallet = get_or_create_crystal_wallet(user_id)
        db.session.flush()

        wallet.add_crystals(
            amount=amount,
            usage_type=usage_type,
            description=f'{description} (by admin {admin_id})',
        )
        db.session.commit()

        return jsonify({
            'success': True,
            'crystal_wallet': wallet.to_dict(),
            'granted': amount
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500