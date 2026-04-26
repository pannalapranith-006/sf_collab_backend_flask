"""
Mentorship Routes — SF Collab
================================
Blueprint mounted at /api/mentorship

Public:
  GET  /mentorship/mentors                    — discover mentors (paginated, filtered)
  GET  /mentorship/mentors/<id>               — single mentor profile

Authenticated — mentor management:
  POST /mentorship/register                   — register as mentor
  GET  /mentorship/my-profile                 — my mentor profile
  PUT  /mentorship/my-profile                 — update my mentor profile
  GET  /mentorship/my-requests                — requests I received as mentor
  POST /mentorship/requests/<id>/accept       — accept a request
  POST /mentorship/requests/<id>/decline      — decline a request
  POST /mentorship/requests/<id>/complete     — complete a session (add summary + action items)
  GET  /mentorship/my-earnings                — mentor earnings summary
  POST /mentorship/payout                     — payout earnings to Balance

Authenticated — founder:
  POST /mentorship/request                    — send mentorship request
  GET  /mentorship/my-sent-requests           — requests I sent as founder
  POST /mentorship/requests/<id>/cancel       — cancel my request
  POST /mentorship/sessions/<id>/rate         — rate a completed session
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.mentor import MentorProfile, MentorshipRequest, MentorSession, PLATFORM_FEE_PERCENT
from app.models.idea import Idea
from app.models.startup import Startup
from app.notifications.service import notification_service
from sqlalchemy import desc, or_

mentorship_bp = Blueprint('mentorship', __name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def require_admin(user_id: int) -> bool:
    user = User.query.get(user_id)
    return bool(user and user.is_admin())


# ── MENTOR DISCOVERY ─────────────────────────────────────────────────────────

@mentorship_bp.route('/mentors', methods=['GET'])
def get_mentors():
    """
    Browse approved, active mentors.
    Query params:
      sector, is_free, available, sort (rating|sessions|experience),
      page, per_page, search
    """
    try:
        page      = request.args.get('page', 1, type=int)
        per_page  = min(request.args.get('per_page', 20, type=int), 100)
        sector    = request.args.get('sector', '').strip()
        is_free   = request.args.get('is_free')
        available = request.args.get('available')
        sort      = request.args.get('sort', 'rating')
        search    = request.args.get('search', '').strip()

        query = MentorProfile.query.filter_by(status='approved')

        if available == 'true':
            query = query.filter_by(is_available=True)

        if is_free == 'true':
            query = query.filter_by(is_free=True)

        if sector:
            # JSON contains search — SQLite compatible
            query = query.filter(
                MentorProfile.sector_expertise.contains(sector)
            )

        if search:
            # Search by user name via join
            query = query.join(User, MentorProfile.user_id == User.id).filter(
                or_(
                    User.first_name.ilike(f'%{search}%'),
                    User.last_name.ilike(f'%{search}%'),
                    MentorProfile.bio.ilike(f'%{search}%'),
                )
            )

        sort_map = {
            'rating':     desc(MentorProfile.average_rating),
            'sessions':   desc(MentorProfile.sessions_completed),
            'experience': desc(MentorProfile.experience_years),
            'newest':     desc(MentorProfile.created_at),
        }
        query = query.order_by(sort_map.get(sort, desc(MentorProfile.average_rating)))

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'success': True,
            'mentors': [m.to_dict() for m in pagination.items],
            'pagination': {
                'page': page, 'per_page': per_page,
                'total': pagination.total, 'pages': pagination.pages,
            }
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/mentors/<int:mentor_id>', methods=['GET'])
def get_mentor(mentor_id):
    """Get a single mentor profile."""
    try:
        mentor = MentorProfile.query.get(mentor_id)
        if not mentor or mentor.status != 'approved':
            return jsonify({'success': False, 'error': 'Mentor not found'}), 404

        # Include recent sessions count
        data = mentor.to_dict()

        return jsonify({'success': True, 'mentor': data}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── MENTOR REGISTRATION & PROFILE ────────────────────────────────────────────

@mentorship_bp.route('/register', methods=['POST'])
@jwt_required()
def register_as_mentor():
    """
    Any user can register as a mentor.
    They are immediately approved (status=approved).
    """
    try:
        user_id = int(get_jwt_identity())
        data    = request.get_json() or {}

        existing = MentorProfile.query.filter_by(user_id=user_id).first()
        if existing:
            return jsonify({
                'success': True,
                'mentor': existing.to_dict(),
                'message': 'Already registered as a mentor'
            }), 200

        # Validate required fields
        if not data.get('bio', '').strip():
            return jsonify({'success': False, 'error': 'Bio is required'}), 400

        if not data.get('sector_expertise'):
            return jsonify({'success': False, 'error': 'At least one sector expertise is required'}), 400

        is_free = data.get('is_free', True)
        session_rate_cents = 0
        if not is_free:
            try:
                session_rate_cents = int(round(float(data.get('session_rate', 0)) * 100))
            except (ValueError, TypeError):
                return jsonify({'success': False, 'error': 'Invalid session rate'}), 400
            if session_rate_cents <= 0:
                return jsonify({'success': False, 'error': 'Paid mentors must set a session rate > $0'}), 400

        mentor = MentorProfile(
            user_id=user_id,
            status='approved',
            bio=data['bio'].strip(),
            sector_expertise=data.get('sector_expertise', []),
            experience_years=int(data.get('experience_years', 0)),
            mentorship_style=data.get('mentorship_style', 'conversational'),
            linkedin_url=data.get('linkedin_url', ''),
            website_url=data.get('website_url', ''),
            is_available=data.get('is_available', True),
            available_hours_per_week=int(data.get('available_hours_per_week', 2)),
            is_free=is_free,
            session_rate_cents=session_rate_cents,
        )
        db.session.add(mentor)
        db.session.commit()

        return jsonify({'success': True, 'mentor': mentor.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/my-profile', methods=['GET'])
@jwt_required()
def get_my_mentor_profile():
    """Get my mentor profile."""
    try:
        user_id = int(get_jwt_identity())
        mentor  = MentorProfile.query.filter_by(user_id=user_id).first()
        if not mentor:
            return jsonify({'success': False, 'error': 'Not registered as a mentor'}), 404
        return jsonify({'success': True, 'mentor': mentor.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/my-profile', methods=['PUT'])
@jwt_required()
def update_my_mentor_profile():
    """Update my mentor profile."""
    try:
        user_id = int(get_jwt_identity())
        mentor  = MentorProfile.query.filter_by(user_id=user_id).first()
        if not mentor:
            return jsonify({'success': False, 'error': 'Not registered as a mentor'}), 404

        data = request.get_json() or {}

        updatable = [
            'bio', 'sector_expertise', 'experience_years', 'mentorship_style',
            'linkedin_url', 'website_url', 'is_available', 'available_hours_per_week',
        ]
        for field in updatable:
            if field in data:
                setattr(mentor, field, data[field])

        if 'is_free' in data:
            mentor.is_free = data['is_free']
            if not mentor.is_free and 'session_rate' in data:
                mentor.session_rate_cents = int(round(float(data['session_rate']) * 100))

        db.session.commit()
        return jsonify({'success': True, 'mentor': mentor.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── MENTORSHIP REQUESTS — FOUNDER SENDS ─────────────────────────────────────

@mentorship_bp.route('/request', methods=['POST'])
@jwt_required()
def send_mentorship_request():
    """
    Founder sends a mentorship request.
    Must attach either idea_id or startup_id.
    If mentor is paid, Balance is checked but NOT debited yet
    (payment happens when mentor accepts and session is confirmed).
    """
    try:
        founder_id = int(get_jwt_identity())
        data       = request.get_json() or {}

        mentor_id  = data.get('mentor_id')
        idea_id    = data.get('idea_id')
        startup_id = data.get('startup_id')

        if not mentor_id:
            return jsonify({'success': False, 'error': 'mentor_id is required'}), 400

        if not idea_id and not startup_id:
            return jsonify({'success': False, 'error': 'Must provide idea_id or startup_id'}), 400

        mentor = MentorProfile.query.get(mentor_id)
        if not mentor or not mentor.is_approved():
            return jsonify({'success': False, 'error': 'Mentor not found or not approved'}), 404

        if not mentor.is_available:
            return jsonify({'success': False, 'error': 'Mentor is not currently available'}), 400

        # Check mentor is not requesting themselves
        if mentor.user_id == founder_id:
            return jsonify({'success': False, 'error': 'Cannot request mentorship from yourself'}), 400

        # Check no pending request already exists for same mentor+idea/startup
        existing_q = MentorshipRequest.query.filter_by(
            founder_id=founder_id,
            mentor_id=mentor_id,
        )
        if idea_id:
            existing_q = existing_q.filter_by(idea_id=idea_id)
        elif startup_id:
            existing_q = existing_q.filter_by(startup_id=startup_id)

        existing = existing_q.filter(
            MentorshipRequest.status.in_(['pending', 'accepted'])
        ).first()

        if existing:
            return jsonify({
                'success': False,
                'error': 'You already have an active request with this mentor for this project'
            }), 400

        # Validate idea/startup ownership
        if idea_id:
            idea = Idea.query.get(idea_id)
            if not idea:
                return jsonify({'success': False, 'error': 'Vision not found'}), 404
            if idea.creator_id != founder_id:
                return jsonify({'success': False, 'error': 'You can only request mentorship for your own visions'}), 403

        if startup_id:
            startup = Startup.query.get(startup_id)
            if not startup:
                return jsonify({'success': False, 'error': 'Startup not found'}), 404

        mentorship_mode = data.get('mentorship_mode', 'free_community')
        if not mentor.is_free and mentorship_mode == 'free_community':
            mentorship_mode = 'paid_session'

        req = MentorshipRequest(
            founder_id=founder_id,
            mentor_id=mentor_id,
            idea_id=idea_id,
            startup_id=startup_id,
            message=data.get('message', '').strip(),
            areas_of_help=data.get('areas_of_help', []),
            mentorship_mode=mentorship_mode,
            agreed_rate_cents=mentor.session_rate_cents if not mentor.is_free else 0,
            status='pending',
        )
        db.session.add(req)
        db.session.commit()

        # ── Notify the mentor ──────────────────────────────────────
        project_title = ''
        if idea_id:
            idea = Idea.query.get(idea_id)
            project_title = idea.title if idea else 'a vision'
        elif startup_id:
            startup = Startup.query.get(startup_id)
            project_title = startup.name if startup else 'a startup'

        founder = User.query.get(founder_id)
        notification_service.create_notification(
            user_id=mentor.user_id,
            template_key='MENTORSHIP_REQUEST_RECEIVED',
            actor_id=founder_id,
            entity_type='mentorship_request',
            entity_id=req.id,
            variables={
                'actor_name': f"{founder.first_name} {founder.last_name}" if founder else 'Someone',
                'project_title': project_title,
            },
            link_url='/mentors/dashboard',
        )

        return jsonify({
            'success': True,
            'request': req.to_dict(),
            'message': 'Mentorship request sent successfully'
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/my-sent-requests', methods=['GET'])
@jwt_required()
def get_my_sent_requests():
    """Get all mentorship requests I sent as a founder."""
    try:
        founder_id = int(get_jwt_identity())
        status     = request.args.get('status')

        query = MentorshipRequest.query.filter_by(founder_id=founder_id)
        if status:
            query = query.filter_by(status=status)
        query = query.order_by(desc(MentorshipRequest.created_at))

        reqs = query.all()
        return jsonify({
            'success': True,
            'requests': [r.to_dict() for r in reqs]
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/requests/<int:req_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_request(req_id):
    """Founder cancels their pending request."""
    try:
        founder_id = int(get_jwt_identity())
        req = MentorshipRequest.query.get(req_id)
        if not req:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        if req.founder_id != founder_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        if req.status not in ('pending', 'accepted'):
            return jsonify({'success': False, 'error': f'Cannot cancel a {req.status} request'}), 400

        req.cancel()
        return jsonify({'success': True, 'request': req.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── MENTORSHIP REQUESTS — MENTOR RESPONDS ────────────────────────────────────

@mentorship_bp.route('/my-requests', methods=['GET'])
@jwt_required()
def get_my_mentor_requests():
    """Get all requests I received as a mentor."""
    try:
        user_id = int(get_jwt_identity())
        mentor  = MentorProfile.query.filter_by(user_id=user_id).first()
        if not mentor:
            return jsonify({'success': False, 'error': 'Not registered as a mentor'}), 404

        status = request.args.get('status')
        query  = MentorshipRequest.query.filter_by(mentor_id=mentor.id)
        if status:
            query = query.filter_by(status=status)
        query = query.order_by(desc(MentorshipRequest.created_at))

        reqs = query.all()
        return jsonify({
            'success': True,
            'requests': [r.to_dict() for r in reqs]
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/requests/<int:req_id>/accept', methods=['POST'])
@jwt_required()
def accept_request(req_id):
    """Mentor accepts a mentorship request."""
    try:
        user_id = int(get_jwt_identity())
        mentor  = MentorProfile.query.filter_by(user_id=user_id).first()
        if not mentor:
            return jsonify({'success': False, 'error': 'Not registered as a mentor'}), 403

        req = MentorshipRequest.query.get(req_id)
        if not req or req.mentor_id != mentor.id:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        if req.status != 'pending':
            return jsonify({'success': False, 'error': f'Cannot accept a {req.status} request'}), 400

        # For paid mentorship — check founder has enough Balance
        if req.agreed_rate_cents > 0:
            from app.models.Balance import Balance
            founder_balance = Balance.query.filter_by(user_id=req.founder_id).first()
            if not founder_balance or founder_balance.available < req.agreed_rate_cents:
                return jsonify({
                    'success': False,
                    'error': 'Founder has insufficient Balance for this paid session'
                }), 400

        req.accept()

        # ── Notify the founder ─────────────────────────────────────
        mentor_user = User.query.get(mentor.user_id)
        project_title = ''
        if req.idea_id and req.idea:
            project_title = req.idea.title
        elif req.startup_id and req.startup:
            project_title = req.startup.name

        notification_service.create_notification(
            user_id=req.founder_id,
            template_key='MENTORSHIP_REQUEST_ACCEPTED',
            actor_id=mentor.user_id,
            entity_type='mentorship_request',
            entity_id=req.id,
            variables={
                'mentor_name': f"{mentor_user.first_name} {mentor_user.last_name}" if mentor_user else 'Your mentor',
                'project_title': project_title or 'your project',
            },
            link_url='/mentors',
        )

        return jsonify({
            'success': True,
            'request': req.to_dict(),
            'message': 'Request accepted. Reach out to the founder to schedule your session.'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/requests/<int:req_id>/decline', methods=['POST'])
@jwt_required()
def decline_request(req_id):
    """Mentor declines a request."""
    try:
        user_id = int(get_jwt_identity())
        mentor  = MentorProfile.query.filter_by(user_id=user_id).first()
        if not mentor:
            return jsonify({'success': False, 'error': 'Not registered as a mentor'}), 403

        req  = MentorshipRequest.query.get(req_id)
        if not req or req.mentor_id != mentor.id:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        if req.status != 'pending':
            return jsonify({'success': False, 'error': f'Cannot decline a {req.status} request'}), 400

        data   = request.get_json() or {}
        reason = data.get('reason', '').strip()
        req.decline(reason)

        # ── Notify the founder ─────────────────────────────────────
        mentor_user = User.query.get(mentor.user_id)
        notification_service.create_notification(
            user_id=req.founder_id,
            template_key='MENTORSHIP_REQUEST_DECLINED',
            actor_id=mentor.user_id,
            entity_type='mentorship_request',
            entity_id=req.id,
            variables={
                'mentor_name': f"{mentor_user.first_name} {mentor_user.last_name}" if mentor_user else 'The mentor',
                'reason': reason or 'No reason provided',
            },
            link_url='/mentors',
        )

        return jsonify({'success': True, 'request': req.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/requests/<int:req_id>/complete', methods=['POST'])
@jwt_required()
def complete_session(req_id):
    """
    Mentor marks session as complete and submits feedback.
    For paid sessions: founder's Balance is debited, mentor's Balance is credited.
    For vision requests: readiness score is recalculated.

    Body:
      summary       (str) — session notes
      action_items  (list) — follow-up action items for founder
    """
    try:
        user_id = int(get_jwt_identity())
        mentor  = MentorProfile.query.filter_by(user_id=user_id).first()
        if not mentor:
            return jsonify({'success': False, 'error': 'Not registered as a mentor'}), 403

        req = MentorshipRequest.query.get(req_id)
        if not req or req.mentor_id != mentor.id:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        if req.status != 'accepted':
            return jsonify({'success': False, 'error': 'Can only complete an accepted request'}), 400

        data         = request.get_json() or {}
        summary      = data.get('summary', '').strip()
        action_items = data.get('action_items', [])

        fee_cents    = 0
        mentor_cut   = 0
        platform_fee = 0

        # Handle payment for paid sessions
        if req.agreed_rate_cents > 0:
            from app.models.Balance import Balance
            fee_cents    = req.agreed_rate_cents
            platform_fee = int(fee_cents * PLATFORM_FEE_PERCENT / 100)
            mentor_cut   = fee_cents - platform_fee

            founder_balance = Balance.query.filter_by(user_id=req.founder_id).first()
            if not founder_balance or founder_balance.available < fee_cents:
                return jsonify({'success': False, 'error': 'Founder has insufficient Balance'}), 400

            # Debit founder
            founder_balance.pay(
                cents=fee_cents,
                reference_type='mentorship_session',
                reference_id=str(req_id),
                description=f'Mentorship session payment'
            )

            # Credit mentor
            mentor_balance = Balance.query.filter_by(user_id=mentor.user_id).first()
            if not mentor_balance:
                mentor_balance = Balance(user_id=mentor.user_id)
                db.session.add(mentor_balance)
                db.session.flush()

            mentor_balance.receive(
                cents=mentor_cut,
                reference_type='mentorship_earning',
                reference_id=str(req_id),
                description=f'Mentorship session earning'
            )

            req.payment_status = 'paid'
            mentor.record_session_completed(mentor_cut)
        else:
            mentor.record_session_completed(0)

        # Update mentor startup count if first session with this founder
        prior_sessions = MentorSession.query.filter_by(
            mentor_id=mentor.id,
            founder_id=req.founder_id,
        ).count()
        if prior_sessions == 0:
            mentor.startups_mentored += 1

        # Create session record
        session = MentorSession(
            request_id=req_id,
            mentor_id=mentor.id,
            founder_id=req.founder_id,
            summary=summary,
            action_items=action_items,
            amount_cents=fee_cents,
            platform_fee_cents=platform_fee,
            mentor_cut_cents=mentor_cut,
        )
        db.session.add(session)

        # Mark request complete
        req.complete()

        # Recalculate vision readiness if this was for a vision
        if req.idea_id:
            try:
                idea = Idea.query.get(req.idea_id)
                if idea:
                    # Mentor review adds 10 points to readiness
                    breakdown = idea.readiness_breakdown or {}
                    breakdown['mentor_review'] = 10
                    idea.readiness_breakdown = breakdown
                    idea.readiness_score = min(100, (idea.readiness_score or 0) + 10)
                    session.readiness_impact = 10
            except Exception:
                pass

        db.session.commit()

        # ── Notify the founder ─────────────────────────────────────
        mentor_user = User.query.get(mentor.user_id)
        mentor_name = f"{mentor_user.first_name} {mentor_user.last_name}" if mentor_user else 'Your mentor'

        notification_service.create_notification(
            user_id=req.founder_id,
            template_key='MENTORSHIP_SESSION_COMPLETED',
            actor_id=mentor.user_id,
            entity_type='mentor_session',
            entity_id=session.id,
            variables={'mentor_name': mentor_name},
            link_url='/mentors',
        )

        # Also notify about summary/action items
        if summary or action_items:
            notification_service.create_notification(
                user_id=req.founder_id,
                template_key='MENTORSHIP_SESSION_SUMMARY',
                actor_id=mentor.user_id,
                entity_type='mentor_session',
                entity_id=session.id,
                variables={'mentor_name': mentor_name},
                link_url='/mentors',
            )

        # If vision readiness improved — notify founder
        if req.idea_id and session.readiness_impact > 0:
            notification_service.create_notification(
                user_id=req.founder_id,
                template_key='VISION_READINESS_IMPROVED',
                actor_id=mentor.user_id,
                entity_type='idea',
                entity_id=req.idea_id,
                variables={'points': int(session.readiness_impact)},
                link_url='/ideation',
            )

        return jsonify({
            'success': True,
            'session': session.to_dict(),
            'request': req.to_dict(),
            'message': 'Session marked as complete'
        }), 200

    except ValueError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── SESSION RATING ────────────────────────────────────────────────────────────

@mentorship_bp.route('/sessions/<int:session_id>/rate', methods=['POST'])
@jwt_required()
def rate_session(session_id):
    """Founder rates a completed session."""
    try:
        founder_id = int(get_jwt_identity())
        data       = request.get_json() or {}

        session = MentorSession.query.get(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        if session.founder_id != founder_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        if session.founder_rating is not None:
            return jsonify({'success': False, 'error': 'Already rated'}), 400

        score = data.get('rating')
        if score is None:
            return jsonify({'success': False, 'error': 'rating is required'}), 400

        try:
            score = float(score)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'rating must be a number'}), 400

        if not 1 <= score <= 5:
            return jsonify({'success': False, 'error': 'rating must be 1–5'}), 400

        session.founder_rating = score
        session.founder_review = data.get('review', '').strip() or None

        # Update mentor's average rating
        mentor = MentorProfile.query.get(session.mentor_id)
        if mentor:
            mentor.add_rating(score)

        db.session.commit()

        # ── Notify the mentor ──────────────────────────────────────
        founder = User.query.get(founder_id)
        if mentor:
            notification_service.create_notification(
                user_id=mentor.user_id,
                template_key='MENTORSHIP_RATED',
                actor_id=founder_id,
                entity_type='mentor_session',
                entity_id=session_id,
                variables={
                    'founder_name': f"{founder.first_name} {founder.last_name}" if founder else 'A founder',
                    'rating': score,
                },
                link_url='/mentors/dashboard',
            )

        return jsonify({
            'success': True,
            'session': session.to_dict(),
            'message': 'Rating submitted'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── MENTOR EARNINGS & PAYOUT ─────────────────────────────────────────────────

@mentorship_bp.route('/my-earnings', methods=['GET'])
@jwt_required()
def get_my_earnings():
    """Mentor earnings summary."""
    try:
        user_id = int(get_jwt_identity())
        mentor  = MentorProfile.query.filter_by(user_id=user_id).first()
        if not mentor:
            return jsonify({'success': False, 'error': 'Not registered as a mentor'}), 404

        recent_sessions = MentorSession.query.filter_by(mentor_id=mentor.id)\
            .order_by(desc(MentorSession.created_at)).limit(10).all()

        return jsonify({
            'success': True,
            'earnings': {
                'total_earned': mentor.total_earned_cents / 100,
                'pending_payout': mentor.pending_payout_cents / 100,
                'sessions_completed': mentor.sessions_completed,
                'startups_mentored': mentor.startups_mentored,
                'average_rating': mentor.average_rating,
                'rating_count': mentor.rating_count,
            },
            'recent_sessions': [s.to_dict() for s in recent_sessions],
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/payout', methods=['POST'])
@jwt_required()
def request_payout():
    """Mentor requests payout of pending earnings to their Balance wallet."""
    try:
        user_id = int(get_jwt_identity())
        mentor  = MentorProfile.query.filter_by(user_id=user_id).first()
        if not mentor:
            return jsonify({'success': False, 'error': 'Not registered as a mentor'}), 404

        if mentor.pending_payout_cents <= 0:
            return jsonify({'success': False, 'error': 'No pending earnings to pay out'}), 400

        if mentor.pending_payout_cents < 500:
            return jsonify({
                'success': False,
                'error': f'Minimum payout is $5.00. Current: ${mentor.pending_payout_cents / 100:.2f}'
            }), 400

        amount_cents = mentor.pending_payout_cents

        from app.models.Balance import Balance
        balance = Balance.query.filter_by(user_id=user_id).first()
        if not balance:
            balance = Balance(user_id=user_id)
            db.session.add(balance)
            db.session.flush()

        balance.receive(
            cents=amount_cents,
            reference_type='mentor_payout',
            description=f'Mentorship payout — ${amount_cents / 100:.2f}'
        )

        mentor.pending_payout_cents = 0
        db.session.commit()

        notification_service.create_notification(
            user_id=user_id,
            template_key='MENTOR_PAYOUT_PROCESSED',
            entity_type='payout',
            variables={'amount': f"{amount_cents / 100:.2f}"},
            link_url='/wallet',
        )

        return jsonify({
            'success': True,
            'paid_out': amount_cents / 100,
            'message': f'${amount_cents / 100:.2f} added to your Balance wallet'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── ADMIN ─────────────────────────────────────────────────────────────────────

@mentorship_bp.route('/admin/mentors', methods=['GET'])
@jwt_required()
def admin_list_mentors():
    """Admin: list all mentors."""
    try:
        user_id = int(get_jwt_identity())
        if not require_admin(user_id):
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        mentors = MentorProfile.query.order_by(desc(MentorProfile.created_at)).all()
        return jsonify({'success': True, 'mentors': [m.to_dict() for m in mentors]}), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@mentorship_bp.route('/admin/mentors/<int:mentor_id>/status', methods=['PUT'])
@jwt_required()
def admin_update_mentor_status(mentor_id):
    """Admin: approve or suspend a mentor."""
    try:
        user_id = int(get_jwt_identity())
        if not require_admin(user_id):
            return jsonify({'success': False, 'error': 'Admin access required'}), 403

        mentor = MentorProfile.query.get(mentor_id)
        if not mentor:
            return jsonify({'success': False, 'error': 'Mentor not found'}), 404

        data   = request.get_json() or {}
        status = data.get('status')
        if status not in ('approved', 'suspended', 'pending'):
            return jsonify({'success': False, 'error': 'status must be approved, suspended, or pending'}), 400

        mentor.status = status
        db.session.commit()

        return jsonify({'success': True, 'mentor': mentor.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500