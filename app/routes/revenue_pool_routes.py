from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.utils.helper import success_response, error_response
from app.services.revenue_pool_service import (
    create_pool,
    update_pool_financials,
    calculate_pool,
    lock_pool,
    mark_pool_paid as mark_pool_paid_service
)
from app.middleware import workspace_admin_required

revenue_pool_bp = Blueprint('revenue_pool', __name__)

@revenue_pool_bp.route('/workspaces/<int:workspace_id>/revenue-pools', methods=['POST'])
@jwt_required()
@workspace_admin_required
def create_revenue_pool(workspace_id):
    data = request.get_json()
    period_start = data.get('period_start')
    period_end = data.get('period_end')
    gross_revenue = data.get('gross_revenue', 0)
    refunds = data.get('refunds', 0)
    chargebacks = data.get('chargebacks', 0)
    exclusions = data.get('manual_exclusions', 0)
    team_share = data.get('team_share_percentage', 40.0)

    if not period_start or not period_end:
        return error_response(message='period_start and period_end are required', status=400)

    try:
        from datetime import datetime as dt
        ps = dt.strptime(period_start, '%Y-%m-%d').date()
        pe = dt.strptime(period_end, '%Y-%m-%d').date()
        pool = create_pool(workspace_id, ps, pe, gross_revenue, refunds, chargebacks, exclusions, team_share)
        return success_response(message='Revenue pool created', data={
            'id': pool.id,
            'eligible_revenue': pool.eligible_revenue,
            'team_pool_amount': pool.team_pool_amount,
            'status': pool.status
        }, status=201)
    except ValueError as e:
        return error_response(message=str(e), status=400)

@revenue_pool_bp.route('/workspaces/<int:workspace_id>/revenue-pools/<int:pool_id>', methods=['PUT'])
@jwt_required()
@workspace_admin_required
def update_revenue_pool(workspace_id, pool_id):
    data = request.get_json()
    try:
        pool = update_pool_financials(
            pool_id,
            gross_revenue=data.get('gross_revenue'),
            refunds=data.get('refunds'),
            chargebacks=data.get('chargebacks'),
            exclusions=data.get('manual_exclusions'),
            team_share=data.get('team_share_percentage')
        )
        return success_response(message='Revenue pool updated', data={
            'id': pool.id,
            'eligible_revenue': pool.eligible_revenue,
            'team_pool_amount': pool.team_pool_amount,
            'status': pool.status
        })
    except ValueError as e:
        return error_response(message=str(e), status=400)

@revenue_pool_bp.route('/workspaces/<int:workspace_id>/revenue-pools/<int:pool_id>/calculate', methods=['POST'])
@jwt_required()
@workspace_admin_required
def calculate_revenue_pool(workspace_id, pool_id):
    try:
        pool = calculate_pool(pool_id)
        return success_response(message='Revenue pool calculated', data={
            'id': pool.id,
            'eligible_revenue': pool.eligible_revenue,
            'team_pool_amount': pool.team_pool_amount,
            'status': pool.status
        })
    except ValueError as e:
        return error_response(message=str(e), status=400)

@revenue_pool_bp.route('/workspaces/<int:workspace_id>/revenue-pools/<int:pool_id>/lock', methods=['POST'])
@jwt_required()
@workspace_admin_required
def lock_revenue_pool(workspace_id, pool_id):
    try:
        pool = lock_pool(pool_id)
        return success_response(message='Revenue pool locked', data={'id': pool.id, 'status': pool.status})
    except ValueError as e:
        return error_response(message=str(e), status=400)

@revenue_pool_bp.route('/workspaces/<int:workspace_id>/revenue-pools/<int:pool_id>/mark-paid', methods=['POST'])
@jwt_required()
@workspace_admin_required
def mark_pool_paid(workspace_id, pool_id):
    try:
        pool = mark_pool_paid_service(pool_id)
        return success_response(message='Revenue pool marked as paid', data={'id': pool.id, 'status': pool.status})
    except ValueError as e:
        return error_response(message=str(e), status=400)