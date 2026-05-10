from flask import Blueprint, request, jsonify
from datetime import datetime

def utc_now_str() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def paginate(query, page=1, per_page=10):
    """Helper function for pagination"""
    page = int(page)
    per_page = int(per_page)
    
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    total = query.count()
    
    return {
        'items': items,
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': (total + per_page - 1) // per_page
    }


def success_response(data=None, message="Success", status=200):
    """Helper function for success responses"""
    response = {'success': True, 'message': message}
    if data is not None:
        response['data'] = data
    return jsonify(response), status


def error_response(message="Error occurred", status=400, data=None):
    """Helper function for error responses"""
    response = {'success': False, 'error': message}
    if data is not None:
        response['data'] = data
    return jsonify(response), status
