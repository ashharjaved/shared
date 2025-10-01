# /src/shared/http/responses.py
"""
HTTP response helpers (error contract + success envelopes).

- ok(data, status=200, headers=None)
- created(data, location=None)
- no_content()
- error_response(app_error, correlation_id)
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from starlette.responses import JSONResponse, Response

from ..errors import DomainError

def ok(data: Any, status: int = 200, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    return JSONResponse({"data": data}, status_code=status, headers=headers or {})

def created(data: Any, location: Optional[str] = None) -> JSONResponse:
    headers = {}
    if location:
        headers["Location"] = location
    return JSONResponse({"data": data}, status_code=201, headers=headers)

def no_content() -> Response:
    return Response(status_code=204)

def error_response(err: DomainError, correlation_id: Optional[str]) -> JSONResponse:
    payload = err.to_payload(correlation_id=correlation_id or "")
    return JSONResponse({"error": payload}, status_code=err.http_status)
