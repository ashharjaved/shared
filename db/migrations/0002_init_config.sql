-- ============================================================================
-- Stage-2: Core Platform — Multi-Tenant Configuration (DB Schema)
-- PostgreSQL 14+ | RLS via jwt_tenant() | Outbox notify | Idempotent-ish
-- ============================================================================

-- 0) Extensions (for gen_random_uuid, json helpers)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Helper: jwt_tenant() -> UUID from GUC 'app.jwt_tenant'
--    If your project already defines jwt_tenant(), this block is skipped.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE p.proname = 'jwt_tenant'
      AND n.nspname = 'public'
      AND pg_get_function_result(p.oid) = 'uuid'
      AND pg_get_function_arguments(p.oid) = ''
  ) THEN
    EXECUTE $fn$
      CREATE FUNCTION public.jwt_tenant()
      RETURNS uuid
      LANGUAGE plpgsql
      STABLE
      AS $$
      DECLARE
        v text;
      BEGIN
        -- Reads the per-session tenant context (set by the API layer).
        v := current_setting('app.jwt_tenant', true);
        IF v IS NULL OR v = '' THEN
          RETURN NULL; -- No tenant context set
        END IF;
        RETURN v::uuid;
      END;
      $$;
    $fn$;
  END IF;
END$$;

-- 2) Enums
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'config_type_enum') THEN
    CREATE TYPE config_type_enum AS ENUM ('GENERAL','SECURITY','BILLING');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'rate_limit_scope_enum') THEN
    CREATE TYPE rate_limit_scope_enum AS ENUM ('TENANT','GLOBAL');
  END IF;
END$$;

-- 3) Utility trigger functions (idempotent CREATE OR REPLACE)

-- 3.1) set_updated_at(): keep updated_at fresh on UPDATE
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$;

-- 3.2) ensure_tenant_id(): enforce tenant isolation rules
--      - For tenant_configurations: tenant_id must match jwt_tenant(); if NULL on INSERT, auto-fill from jwt_tenant().
--      - For rate_limit_policies: allow NULL (GLOBAL scope), otherwise enforce match to jwt_tenant().
CREATE OR REPLACE FUNCTION public.ensure_tenant_id()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_ctx uuid := jwt_tenant();
BEGIN
  -- UPDATE must not cross-tenant
  IF TG_OP = 'UPDATE' AND NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
    RAISE EXCEPTION 'Tenant change is not allowed (RLS guard)'
      USING ERRCODE = '42501';
  END IF;

  IF TG_TABLE_NAME = 'tenant_configurations' THEN
    IF v_ctx IS NULL THEN
      RAISE EXCEPTION 'Missing RLS context: app.jwt_tenant is not set'
        USING ERRCODE = '42501';
    END IF;

    IF TG_OP = 'INSERT' AND NEW.tenant_id IS NULL THEN
      NEW.tenant_id := v_ctx;
    END IF;

    IF NEW.tenant_id IS DISTINCT FROM v_ctx THEN
      RAISE EXCEPTION 'Tenant mismatch (expected % but got %)', v_ctx, NEW.tenant_id
        USING ERRCODE = '42501';
    END IF;

  ELSE -- Applies to rate_limit_policies
    -- Allow GLOBAL rows (tenant_id IS NULL).
    IF NEW.tenant_id IS NULL THEN
      RETURN NEW;
    END IF;

    IF v_ctx IS NULL THEN
      RAISE EXCEPTION 'Missing RLS context: app.jwt_tenant is not set'
        USING ERRCODE = '42501';
    END IF;

    IF NEW.tenant_id IS DISTINCT FROM v_ctx THEN
      RAISE EXCEPTION 'Tenant mismatch (expected % but got %)', v_ctx, NEW.tenant_id
        USING ERRCODE = '42501';
    END IF;
  END IF;

  RETURN NEW;
END
$$;
-- 3.3) write_outbox_event(): notify downstream to invalidate caches / consume events
--      Uses LISTEN/NOTIFY to avoid tight coupling with an outbox table.
CREATE OR REPLACE FUNCTION public.write_outbox_event(entity_name text, event_name text, payload jsonb DEFAULT '{}'::jsonb)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  -- Channel name kept generic; consumers can bridge to a durable outbox if desired.
  PERFORM pg_notify(
    'outbox_event',
    jsonb_build_object(
      'aggregate_type', entity_name,
      'event_type',     event_name,
      'payload',        COALESCE(payload, '{}'::jsonb),
      'occurred_at',    to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
    )::text
  );
END
$$;

-- 3.4) enable_tenant_rls(table_name): enable RLS + create tenant policy if missing
CREATE OR REPLACE FUNCTION public.enable_tenant_rls(table_name text)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_exists boolean;
  v_sql text;
  v_policy_name text := 'tenant_isolation_policy';
BEGIN
  -- Enable RLS
  v_sql := format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
  EXECUTE v_sql;

  -- Create policy if not present
  SELECT EXISTS (
    SELECT 1
    FROM pg_policy pol
    JOIN pg_class c ON c.oid = pol.polrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE pol.polname = v_policy_name
      AND c.relname = table_name
      AND n.nspname = 'public'
  ) INTO v_exists;

  IF NOT v_exists THEN
    IF table_name = 'rate_limit_policies' THEN
      v_sql := format(
        'CREATE POLICY %I ON %I USING (tenant_id = jwt_tenant() OR tenant_id IS NULL) WITH CHECK (tenant_id = jwt_tenant())',
        v_policy_name, table_name
      );
    ELSE
      v_sql := format(
        'CREATE POLICY %I ON %I USING (tenant_id = jwt_tenant()) WITH CHECK (tenant_id = jwt_tenant())',
        v_policy_name, table_name
      );
    END IF;
    EXECUTE v_sql;
  END IF;
END
$$;
-- 4) Tables
-- 4.1) tenant_configurations
CREATE TABLE IF NOT EXISTS public.tenant_configurations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  config_key    varchar(100) NOT NULL,
  config_value  jsonb        NOT NULL,
  config_type   config_type_enum NOT NULL DEFAULT 'GENERAL',
  is_encrypted  boolean      NOT NULL DEFAULT false,
  created_at    timestamptz  NOT NULL DEFAULT now(),
  updated_at    timestamptz  NOT NULL DEFAULT now(),
  deleted_at    timestamptz  NULL
);

-- FK → tenants(id) (assumes tenants exists from Stage-1)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'public'
      AND table_name = 'tenant_configurations'
      AND constraint_name = 'fk_tenant_config__tenant'
  ) THEN
    ALTER TABLE public.tenant_configurations
      ADD CONSTRAINT fk_tenant_config__tenant
      FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;
  END IF;
END$$;

-- Comments / compliance stance
COMMENT ON TABLE  public.tenant_configurations IS
  'Per-tenant configuration KV with JSONB values. Use is_encrypted=true for secrets; no PHI allowed in config_value.';
COMMENT ON COLUMN public.tenant_configurations.config_value IS
  'JSONB configuration value. If is_encrypted=true, value must be envelope-encrypted ciphertext (POLICIES.md).';
COMMENT ON COLUMN public.tenant_configurations.is_encrypted IS
  'Indicates whether config_value is ciphertext (envelope encryption).';
COMMENT ON COLUMN public.tenant_configurations.deleted_at IS
  'Soft delete timestamp. Application should not return soft-deleted rows.';

-- Unique (tenant_id, config_key) via pre-created unique index (named as requested)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class WHERE relname = 'ix_tenant_config__tenant_key'
  ) THEN
    CREATE UNIQUE INDEX ix_tenant_config__tenant_key
      ON public.tenant_configurations(tenant_id, config_key);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'public'
      AND table_name = 'tenant_configurations'
      AND constraint_name = 'uq_tenant_config'
  ) THEN
    ALTER TABLE public.tenant_configurations
      ADD CONSTRAINT uq_tenant_config UNIQUE USING INDEX ix_tenant_config__tenant_key;
  END IF;
END$$;

-- JSONB GIN index for config_value queries
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class WHERE relname = 'ix_tenant_config__value_gin'
  ) THEN
    CREATE INDEX ix_tenant_config__value_gin
      ON public.tenant_configurations
      USING GIN (config_value);
  END IF;
END$$;

-- Optional key format guard (uncomment if you enforce naming)
-- ALTER TABLE public.tenant_configurations
--   ADD CONSTRAINT ck_tenant_config__key_format
--   CHECK (config_key ~ '^[a-z0-9_.:-]{1,100}$');

-- 4.2) rate_limit_policies
CREATE TABLE IF NOT EXISTS public.rate_limit_policies (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NULL,  -- NULL => GLOBAL
  scope                rate_limit_scope_enum NOT NULL,
  requests_per_minute  integer NOT NULL,
  burst_limit          integer NOT NULL DEFAULT 0,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL
);

-- FK → tenants(id) with NULL allowed
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'public'
      AND table_name = 'rate_limit_policies'
      AND constraint_name = 'fk_rate_limit__tenant'
  ) THEN
    ALTER TABLE public.rate_limit_policies
      ADD CONSTRAINT fk_rate_limit__tenant
      FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;
  END IF;
END$$;

COMMENT ON TABLE  public.rate_limit_policies IS
  'Per-tenant and GLOBAL (tenant_id NULL) rate limiting policies for API access.';
COMMENT ON COLUMN public.rate_limit_policies.tenant_id IS
  'NULL => GLOBAL policy; otherwise tenant-scoped.';
COMMENT ON COLUMN public.rate_limit_policies.requests_per_minute IS
  'Allowed requests per minute for the (tenant,scope).';
COMMENT ON COLUMN public.rate_limit_policies.burst_limit IS
  'Token-bucket burst size (additional short spikes tolerated).';

-- Unique (tenant_id, scope) via requested index + constraint
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class WHERE relname = 'ix_rate_limit__tenant_scope'
  ) THEN
    CREATE UNIQUE INDEX ix_rate_limit__tenant_scope
      ON public.rate_limit_policies(tenant_id, scope);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE constraint_schema = 'public'
      AND table_name = 'rate_limit_policies'
      AND constraint_name = 'uq_rate_limit'
  ) THEN
    ALTER TABLE public.rate_limit_policies
      ADD CONSTRAINT uq_rate_limit UNIQUE USING INDEX ix_rate_limit__tenant_scope;
  END IF;

  -- Ensure at most one GLOBAL policy per scope (because NULLs do not collide in UNIQUE)
  IF NOT EXISTS (
    SELECT 1 FROM pg_class WHERE relname = 'ix_rate_limit__global_scope_unique'
  ) THEN
    CREATE UNIQUE INDEX ix_rate_limit__global_scope_unique
      ON public.rate_limit_policies(scope)
      WHERE tenant_id IS NULL;
  END IF;
END$$;

-- 5) RLS enablement & policies
SELECT public.enable_tenant_rls('tenant_configurations');
SELECT public.enable_tenant_rls('rate_limit_policies');

-- 6) Outbox trigger wrappers (to sanitize payloads and avoid leaking secrets)

-- tenant_configurations outbox wrapper: DO NOT emit config_value
CREATE OR REPLACE FUNCTION public.outbox_tenant_configuration_changed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM public.write_outbox_event(
    'TenantConfiguration',
    'ConfigChanged',
    jsonb_build_object(
      'id', NEW.id,
      'tenant_id', NEW.tenant_id,
      'config_key', NEW.config_key,
      'config_type', NEW.config_type,
      'is_encrypted', NEW.is_encrypted,
      'ts', to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
    )
  );
  RETURN NULL;
END
$$;

-- rate_limit_policies outbox wrapper
CREATE OR REPLACE FUNCTION public.outbox_rate_limit_policy_changed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM public.write_outbox_event(
    'RateLimitPolicy',
    'RateLimitChanged',
    jsonb_build_object(
      'id', NEW.id,
      'tenant_id', NEW.tenant_id,
      'scope', NEW.scope,
      'requests_per_minute', NEW.requests_per_minute,
      'burst_limit', NEW.burst_limit,
      'ts', to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
    )
  );
  RETURN NULL;
END
$$;

-- 7) Triggers

-- tenant_configurations
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_config__updated_at'
  ) THEN
    CREATE TRIGGER trg_config__updated_at
      BEFORE UPDATE ON public.tenant_configurations
      FOR EACH ROW
      EXECUTE FUNCTION public.set_updated_at();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_config__tenant_guard'
  ) THEN
    CREATE TRIGGER trg_config__tenant_guard
      BEFORE INSERT OR UPDATE ON public.tenant_configurations
      FOR EACH ROW
      EXECUTE FUNCTION public.ensure_tenant_id();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_config__outbox'
  ) THEN
    CREATE TRIGGER trg_config__outbox
      AFTER INSERT OR UPDATE ON public.tenant_configurations
      FOR EACH ROW
      EXECUTE FUNCTION public.outbox_tenant_configuration_changed();
  END IF;
END$$;

-- rate_limit_policies
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rate_limit__updated_at'
  ) THEN
    CREATE TRIGGER trg_rate_limit__updated_at
      BEFORE UPDATE ON public.rate_limit_policies
      FOR EACH ROW
      EXECUTE FUNCTION public.set_updated_at();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rate_limit__tenant_guard'
  ) THEN
    CREATE TRIGGER trg_rate_limit__tenant_guard
      BEFORE INSERT OR UPDATE ON public.rate_limit_policies
      FOR EACH ROW
      EXECUTE FUNCTION public.ensure_tenant_id();
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_rate_limit__outbox'
  ) THEN
    CREATE TRIGGER trg_rate_limit__outbox
      AFTER INSERT OR UPDATE ON public.rate_limit_policies
      FOR EACH ROW
      EXECUTE FUNCTION public.outbox_rate_limit_policy_changed();
  END IF;
END$$;

-- 8) Optional RLS smoke check (non-failing)
--    Validates that policy compiles and jwt_tenant() is callable.
DO $$
DECLARE
  _dummy int;
BEGIN
  -- Set a temporary tenant context and do harmless queries.
  PERFORM set_config('app.jwt_tenant', '00000000-0000-0000-0000-000000000000', true);
  SELECT count(*) INTO _dummy FROM public.tenant_configurations WHERE tenant_id = public.jwt_tenant();
  SELECT count(*) INTO _dummy FROM public.rate_limit_policies WHERE (tenant_id = public.jwt_tenant() OR tenant_id IS NULL);
  -- Reset
  PERFORM set_config('app.jwt_tenant', NULL, true);
END
$$;

-- ============================================================================
-- End of Stage-2 Migration
-- ============================================================================
