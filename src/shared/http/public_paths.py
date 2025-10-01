# PUBLIC_PATHS = {
#     "/", "/docs", "/openapi.json",
#     "/_health/db", "/_health/redis",
#     "/api/messaging/webhook",
#     "/api/identity/auth",
#     "/favicon.ico",
#     "/api/identity/tenants"
# }

# def is_public_path(path: str) -> bool:
    # return any(path == p or (p != "/" and path.startswith(p.rstrip("/") + "/")) for p in PUBLIC_PATHS)
# src/shared/http/paths.py
# src/shared/http/public_paths.py
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/openapi.json",
    "/_health",
    "/_health/db", 
    "/_health/redis",
    "/api/messaging/webhook",
    "/api/identity/auth",
    "/favicon.ico",
    "/api/identity/tenants",
    "/v1/wa/webhook"
}

def is_public_path(path: str) -> bool:
    """Check if a path is public and doesn't require authentication."""
    return any(
        path == public_path or path.startswith(public_path.rstrip("/") + "/")
        for public_path in PUBLIC_PATHS
    )