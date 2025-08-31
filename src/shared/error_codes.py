# src/shared/error_codes.py
# Central mapping that aligns with your Error Contract.
# Keep keys stable—API/Mobile clients rely on these.
ERROR_CODES = {
    # ─── Validation & Requests ──────────────────────────────────────────────
    "validation_error": {
        "http": 400,
        "message": "Validation failed for one or more fields."
    },
    "invalid_request": {
        "http": 422,
        "message": "Invalid request payload."
    },
    "missing_request": {
        "http": 400,
        "message": "Missing request payload."
    },
    "invalid_request_format": {
        "http": 400,
        "message": "Invalid request format."
    },
    "invalid_request_type": {
        "http": 400,
        "message": "Invalid request type."
    },
    "invalid_request_data": {
        "http": 400,
        "message": "Invalid request data."
    },
    "invalid_request_field": {
        "http": 400,
        "message": "Invalid request field."
    },
    "invalid_request_value": {
        "http": 400,
        "message": "Invalid request value."
    },

    # ─── Authentication & Authorization ────────────────────────────────────
    "unauthorized": {
        "http": 401,
        "message": "Unauthorized. Please provide valid credentials."
    },
    "invalid_credentials": {
        "http": 401,
        "message": "Invalid email or password."
    },
    "account_inactive": {
        "http": 403,
        "message": "Account inactive."
    },
    "account_locked": {
        "http": 403,
        "message": "Account locked due to too many failed login attempts."
    },
    "forbidden": {
        "http": 403,
        "message": "You are not allowed to perform this action."
    },
    "expired_token": {
        "http": 401,
        "message": "Token has expired."
    },
    "invalid_token": {
        "http": 401,
        "message": "Invalid token."
    },
    "token_revoked": {
        "http": 401,
        "message": "Token has been revoked."
    },
    "token_missing": {
        "http": 401,
        "message": "Token is missing."
    },
    "token_invalid": {
        "http": 401,
        "message": "Token is invalid." 
    },

    # ─── Identity & Tenant Management ──────────────────────────────────────
    "user_not_found": {
        "http": 404,
        "message": "User not found."
    },
    "tenant_not_found": {
        "http": 404,
        "message": "Tenant not found."
    },
    "email_taken": {
        "http": 409,
        "message": "Email already in use for this tenant."
    },
    "tenant_conflict": {
        "http": 409,
        "message": "Tenant already exists with this name."
    },
    "role_change_not_allowed": {
        "http": 403,
        "message": "Role change not permitted."
    },

    # ─── Idempotency & Conflicts ───────────────────────────────────────────
    "conflict": {
        "http": 409,
        "message": "Conflict with existing resource."
    },
    "idempotency_conflict": {
        "http": 409,
        "message": "Duplicate request detected (idempotency conflict)."
    },

    # ─── RLS / Tenant Context ──────────────────────────────────────────────
    "rls_not_set": {
        "http": 500,
        "message": "Tenant context (RLS) not set."
    },

    # ─── Rate Limiting ─────────────────────────────────────────────────────
    "rate_limited": {
        "http": 429,
        "message": "Too many requests. Please try again later."
    },

    # ─── Internal ──────────────────────────────────────────────────────────
    "internal_error": {
        "http": 500,
        "message": "An unexpected error occurred. Please try again later."
    },
    "crypto_error":{
        "http": 500,
        "message": "An unexpected error occurred. Please try again later."
    }
}