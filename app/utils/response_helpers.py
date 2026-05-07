# app/utils/response_helpers.py  (assumed helper module)
from flask import jsonify

def success_response(data, status_code=200):
    return jsonify(data), status_code

def error_response(message, status_code=400):
    return jsonify({"error": message}), status_code