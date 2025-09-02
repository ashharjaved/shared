-- db/migrations/0001_init_identity.sql

-- =============================================================================
-- Stage-1: Identity & Access — Tenants, Users, RBAC, JWT
-- This merged migration integrates the review fixes: enums, UUID defaults,
-- RLS helper with USING + WITH CHECK, tenant guard trigger with error-contract
-- messages, compliance COMMENTs, and minimal outbox (optional).
-- Idempotent where possible.
-- =============================================================================

-- ========== Extensions =======================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "citext";

-- ========== Enums ============================================================
DO $$ BEGIN
  CREATE TYPE user_role_enum AS ENUM ('SUPER_ADMIN', 'RESELLER_ADMIN', 'TENANT_ADMIN', 'STAFF');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE tenant_type_enum AS ENUM ('PLATFORM_OWNER', 'RESELLER', 'CLIENT');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE subscription_plan_enum AS ENUM ('FREE', 'BASIC', 'PREMIUM', 'ENTERPRISE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ========== Helpers: GUC access =============================================
CREATE OR REPLACE FUNCTION jwt_tenant() RETURNS UUID AS $$
DECLARE
  v text := current_setting('app.jwt_tenant', true);
BEGIN
  IF v IS NULL THEN
    RETURN NULL;
  END IF;
  RETURN v::uuid;
EXCEPTION WHEN others THEN
  RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ========== Triggers: updated_at ============================================
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ========== Triggers: tenant guard ==========================================
CREATE OR REPLACE FUNCTION ensure_tenant_id() RETURNS TRIGGER AS $$
DECLARE
  guc text := current_setting('app.jwt_tenant', true);
BEGIN
  -- Auto-fill from GUC on INSERT if not provided
  IF TG_OP = 'INSERT' AND NEW.tenant_id IS NULL THEN
    NEW.tenant_id = guc::uuid;
    IF NEW.tenant_id IS NULL THEN
      RAISE EXCEPTION USING
        ERRCODE = 'P0001',
        MESSAGE = 'ERR_TENANT_MISSING: tenant_id cannot be null and app.jwt_tenant GUC is not set';
    END IF;
  END IF;

  -- Enforce match when GUC is present
  IF guc IS NOT NULL THEN
    IF NEW.tenant_id IS DISTINCT FROM guc::uuid THEN
      RAISE EXCEPTION USING
        ERRCODE = 'P0001',
        MESSAGE = format('ERR_TENANT_MISMATCH: tenant_id %s does not match app.jwt_tenant %s', NEW.tenant_id, guc);
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ========== RLS Helper =======================================================
CREATE OR REPLACE FUNCTION enable_tenant_rls(p_table regclass) RETURNS void AS $$
BEGIN
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', p_table);
  EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_policy ON %s', p_table);
  -- Strict policy: both read filter and write check
  EXECUTE format(
    'CREATE POLICY tenant_isolation_policy ON %s
       USING  (tenant_id = jwt_tenant())
       WITH CHECK (tenant_id = jwt_tenant())',
    p_table
  );
END;
$$ LANGUAGE plpgsql;

-- ========== Tables ===========================================================
-- Global tenants table (no RLS)
CREATE TABLE IF NOT EXISTS tenants (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                TEXT UNIQUE NOT NULL,
  type                tenant_type_enum NOT NULL,
  parent_tenant_id    UUID NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  plan                subscription_plan_enum NULL,
  is_active           BOOLEAN NOT NULL DEFAULT true,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for tenants
CREATE INDEX IF NOT EXISTS idx_tenants_type   ON tenants(type);
CREATE INDEX IF NOT EXISTS idx_tenants_parent ON tenants(parent_tenant_id);

-- Tenant-scoped users table (RLS)
CREATE TABLE IF NOT EXISTS users (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  email                 CITEXT NOT NULL,
  password_hash         TEXT NOT NULL,
  role                  user_role_enum NOT NULL,
  is_active             BOOLEAN NOT NULL DEFAULT true,
  is_verified           BOOLEAN NOT NULL DEFAULT false,
  failed_login_attempts INTEGER NOT NULL DEFAULT 0,
  last_login            TIMESTAMPTZ NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email),
  CONSTRAINT chk_failed_login_attempts_nonneg CHECK (failed_login_attempts >= 0);
);

-- Pragmatic index for role scans within a tenant
CREATE INDEX IF NOT EXISTS idx_users_tenant_role ON users(tenant_id, role);
CREATE INDEX IF NOT EXISTS idx_users_tenant        ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant_active ON users(tenant_id, is_active);

-- =============================================================================
-- ========== Idempotency (NON-NEGOTIABLE) ====================================
CREATE TABLE IF NOT EXISTS idempotency_keys (
  tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  endpoint    TEXT NOT NULL,
  key         TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, endpoint, key)
);

CREATE OR REPLACE FUNCTION ensure_idempotency(p_endpoint TEXT, p_key TEXT)
RETURNS void AS $$
BEGIN
  INSERT INTO idempotency_keys (tenant_id, endpoint, key)
  VALUES (jwt_tenant(), p_endpoint, p_key);
EXCEPTION WHEN unique_violation THEN
  RAISE EXCEPTION USING
    ERRCODE = 'P0001',
    MESSAGE = 'ERR_IDEMPOTENCY_CONFLICT: duplicate request';
END;
$$ LANGUAGE plpgsql;

-- ========== Triggers Wiring ==================================================
DROP TRIGGER IF EXISTS tr_tenants_updated_at ON tenants;
CREATE TRIGGER tr_tenants_updated_at
  BEFORE UPDATE ON tenants
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS tr_users_updated_at ON users;
CREATE TRIGGER tr_users_updated_at
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS tr_users_ensure_tenant ON users;
CREATE TRIGGER tr_users_ensure_tenant
  BEFORE INSERT OR UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();

-- ========== RLS Enforcement ==================================================
SELECT enable_tenant_rls('users'::regclass);
-- Enforce RLS on tenant-scoped idempotency keys
SELECT enable_tenant_rls('idempotency_keys'::regclass);

-- ========== Compliance / Auditability =======================================
COMMENT ON TABLE tenants IS 'Global registry of tenants (platform/reseller/client). No PHI/PII beyond business metadata.';
COMMENT ON COLUMN tenants.plan IS 'Subscription plan (enum). Pricing/limits defined elsewhere.';

COMMENT ON TABLE users IS 'Tenant-scoped identities. Store only password HASH (Argon2id). Absolutely no PHI.';
COMMENT ON COLUMN users.email IS 'Login identifier; CITEXT ensures case-insensitivity. Unique per tenant.';
COMMENT ON COLUMN users.password_hash IS 'Argon2id hash (e.g., m=65536,t=3,p=4). No plaintext; rotate on policy changes.';
COMMENT ON COLUMN users.tenant_id IS 'RLS boundary. All access filtered by jwt_tenant().';

-- ========== Minimal Outbox (Optional; keep if Stage-1 requires events) ======
-- If outbox is defined elsewhere, this block is harmlessly idempotent or can be removed.
CREATE TABLE IF NOT EXISTS outbox_events (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aggregate_type TEXT NOT NULL,
  aggregate_id   UUID NOT NULL,
  event_type     TEXT NOT NULL,
  payload        JSONB NOT NULL,
  occurred_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at   TIMESTAMPTZ NULL
);

CREATE OR REPLACE FUNCTION enqueue_user_created() RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO outbox_events (aggregate_type, aggregate_id, event_type, payload)
  VALUES ('User', NEW.id, 'UserCreated', jsonb_build_object(
    'tenant_id', NEW.tenant_id,
    'user_id',   NEW.id,
    'email',     NEW.email,
    'role',      NEW.role
  ));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_users_outbox_created ON users;
CREATE TRIGGER tr_users_outbox_created
  AFTER INSERT ON users
  FOR EACH ROW EXECUTE FUNCTION enqueue_user_created();

-- ========== Optional Seed (LOCAL ONLY) ======================================
/*
-- Seed a platform tenant and super admin (replace UUID + real Argon2id hash)
INSERT INTO tenants (id, name, type, plan, is_active)
VALUES ('00000000-0000-0000-0000-000000000000', 'Platform', 'PLATFORM_OWNER', 'ENTERPRISE', true)
ON CONFLICT (name) DO NOTHING;

-- SET LOCAL app.jwt_tenant='00000000-0000-0000-0000-000000000000';
INSERT INTO users (tenant_id, email, password_hash, role, is_active, is_verified)
VALUES (
  '00000000-0000-0000-0000-000000000000',
  'admin@platform.com',
  '$argon2id$v=19$m=65536,t=3,p=4$REPLACE_ME$REPLACE_ME', -- REAL hash only
  'SUPER_ADMIN',
  true,
  true
) ON CONFLICT (tenant_id, email) DO NOTHING;
*/