# import time
# from jose import jwt

# # --- EDIT THESE THREE ---
# SECRET    = "super-long-very-random-secret-change-me-now"  # same as JWT_SECRET if you created a .env
# TENANT_ID = "d5854a78-2991-4761-9c4d-0a2c4eb6d5a9"
# EMAIL     = "owner@example.com"                          # or whatever you used

# # Algorithm
# ALG = "HS256"

# # Type for your owner admin
# ROLE = ["SUPER_ADMIN"]

# now = int(time.time())
# claims = {
#     "sub": EMAIL,
#     "tenant_id": TENANT_ID,
#     "roles": ROLE,
#     "iat": now,
#     "exp": now + 60 * 60 * 24 * 7,  # 12h
# }

# token = jwt.encode(claims, SECRET, algorithm=ALG)
# print(token)

# # eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJvd25lckBleGFtcGxlLmNvbSIsInRlbmFudF9pZCI6ImQ1ODU0YTc4LTI5OTEtNDc2MS05YzRkLTBhMmM0ZWI2ZDVhOSIsInJvbGVzIjpbIlNVUEVSX0FETUlOIl0sImlhdCI6MTc1NTcwNzU3NCwiZXhwIjoxNzU2MzEyMzc0fQ.UpT2QGMRoU4LRixg4fbbLycvCZetZ1VRPXhMfD_p4H4