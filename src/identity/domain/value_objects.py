import enum
class TenantType(str, enum.Enum):
    PLATFORM_OWNER = "PLATFORM_OWNER"
    CLIENT = "CLIENT"
    RESELLER = "RESELLER"

class SubscriptionPlan(str, enum.Enum):
    BASIC = "BASIC"
    STANDARD = "STANDARD"
    ENTERPRISE = "ENTERPRISE"

class SubscriptionStatus(str, enum.Enum):
    ACTIVE    = "ACTIVE"
    PAST_DUE  = "PAST_DUE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    RESELLER_ADMIN = "RESELLER_ADMIN"   
    TENANT_ADMIN = "TENANT_ADMIN"
    STAFF = "STAFF"

