# utils/csv_utils.py
# SFCollab ERP — CSV output helpers
# Keeps Flask's make_response out of services and models

from __future__ import annotations

import csv
import io

from flask import make_response


def flatten(data: dict, prefix: str = "") -> dict:
    """
    Recursively flatten nested dicts into dot-separated keys.
    Lists are skipped — not representable as CSV columns.

    Example:
        {"a": {"b": 1}, "c": [2]}  →  {"a.b": 1}
    """
    out = {}
    for k, v in data.items():
        full_key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(flatten(v, full_key))
        elif not isinstance(v, list):
            out[full_key] = v
    return out


def to_csv_response(data: dict, filename: str):
    """
    Flatten all scalar fields (including nested) into a CSV file download.
    Returns a Flask response with Content-Disposition attachment header.
    """
    flat   = flatten(data)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=flat.keys())
    writer.writeheader()
    writer.writerow(flat)

    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = f"attachment; filename={filename}"
    resp.headers["Content-Type"]        = "text/csv"
    return resp