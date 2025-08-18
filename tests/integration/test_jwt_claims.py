from src.shared.security import issue_token, decode_token
def test_jwt_claims_shape(settings):
    token = issue_token(sub="user-1", tenant_id="ten-1", roles=["ADMIN"])
    payload = decode_token(token)
    for k in ("sub","tenant_id","roles","iat","exp"):
        assert k in payload
