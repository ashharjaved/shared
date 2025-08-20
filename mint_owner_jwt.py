import time
from jose import jwt

# --- EDIT THESE THREE ---
SECRET    = "super-long-very-random-secret-change-me-now"  # same as JWT_SECRET if you created a .env
TENANT_ID = "df72babe-05cc-4a6a-b3a6-7a994e1f8a47"
EMAIL     = "owner@example.com"                            # or whatever you used

# Algorithm
ALG = "HS256"

# Type for your owner admin
TYPE = ["PLATFORM_OWNER"]

now = int(time.time())
claims = {
    "sub": EMAIL,
    "tenant_id": TENANT_ID,
    "roles": TYPE,
    "iat": now,
    "exp": now + 60 * 60 * 24 * 7,  # 12h
}

token = jwt.encode(claims, SECRET, algorithm=ALG)
print(token)

# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJvd25lckBleGFtcGxlLmNvbSIsInRlbmFudF9pZCI6ImRmNzJiYWJlLTA1Y2MtNGE2YS1iM2E2LTdhOTk0ZTFmOGE0NyIsInJvbGVzIjpbIlBMQVRGT1JNX09XTkVSIl0sImlhdCI6MTc1NTY3NTgzNiwiZXhwIjoxNzU2MjgwNjM2fQ.np-TDKJRjlOjXOWYwjzmvGxe8HyJ0gGITSFhz3WoxEg