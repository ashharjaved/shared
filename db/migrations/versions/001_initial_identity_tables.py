"""DEV-1 Unified Patch: RLS contract, triggers, audit append-only, extra cols, plans/subscriptions fixes.

- Remove RLS from tenant (global scope)
- Add tenant_type enum + column on tenant
- Add failed_login_attempts + last_login on user
- Add slug (unique) on plan
- Enable RLS for tenant_plan_subscriptions + policy
- Create/replace helper funcs: jwt_tenant(), set_updated_at(), ensure_tenant_id()
- Attach updated_at + tenant_guard triggers
- Audit log append-only (block UPDATE/DELETE)
- Optional seed: platform owner tenant
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers (adjust to your graph) ---
revision = "003_initial_identity"
down_revision = None  # <-- set to actual rev id of 002 file
branch_labels = None
depends_on = None


def upgrade():
    # ---------- Helpers / Enums ----------
    # jwt_tenant(): read GUC and cast to uuid (NULL if not set)
    op.execute("""
    CREATE OR REPLACE FUNCTION jwt_tenant() RETURNS uuid
    LANGUAGE sql STABLE AS $$
      SELECT NULLIF(current_setting('app.jwt_tenant', true), '')::uuid
    $$;
    """)

    # set_updated_at(): generic touch trigger
    op.execute("""
    CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      NEW.updated_at := NOW();
      RETURN NEW;
    END;
    $$;
    """)

    # ensure_tenant_id(): on INSERT/UPDATE, enforce tenant_id = jwt_tenant(); set if NULL on insert
    op.execute("""
    CREATE OR REPLACE FUNCTION ensure_tenant_id() RETURNS trigger
    LANGUAGE plpgsql AS $$
    DECLARE
      _ctx uuid := jwt_tenant();
    BEGIN
      IF TG_OP = 'INSERT' THEN
        IF NEW.tenant_id IS NULL THEN
          NEW.tenant_id := _ctx;
        ELSIF _ctx IS NOT NULL AND NEW.tenant_id <> _ctx THEN
          RAISE EXCEPTION 'tenant_id mismatch with jwt_tenant()';
        END IF;
        RETURN NEW;
      ELSIF TG_OP = 'UPDATE' THEN
        IF _ctx IS NOT NULL AND NEW.tenant_id <> OLD.tenant_id THEN
          RAISE EXCEPTION 'tenant_id cannot be changed';
        END IF;
        IF _ctx IS NOT NULL AND NEW.tenant_id <> _ctx THEN
          RAISE EXCEPTION 'tenant_id mismatch with jwt_tenant()';
        END IF;
        RETURN NEW;
      END IF;
      RETURN NEW;
    END;
    $$;
    """)

    # tenant_type_enum (guard create)
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tenant_type_enum') THEN
        CREATE TYPE tenant_type_enum AS ENUM ('PLATFORM_OWNER','RESELLER','CLIENT');
      END IF;
    END$$;
    """)

    # ---------- TENANT (global, NO RLS) ----------
    # Remove RLS if present; keep tenant global per spec
    op.execute("ALTER TABLE IF EXISTS tenant DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant;")

    # tenant_type column (nullable at first for safe alter, then backfill/constraint)
    op.add_column("tenant", sa.Column("tenant_type", sa.Enum(name="tenant_type_enum", create_type=False), nullable=True))
    # parent_tenant_id column naming normalization if needed (safe add if missing)
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='tenant' AND column_name='parent_tenant_id'
      ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='tenant' AND column_name='parent_id'
      ) THEN
        ALTER TABLE tenant RENAME COLUMN parent_id TO parent_tenant_id;
      END IF;
    END$$;
    """)

    # Backfill tenant_type if you have legacy rows (default PLATFORM_OWNER for the first tenant)
    op.execute("""
      UPDATE tenant t SET tenant_type='PLATFORM_OWNER'
      WHERE tenant_type IS NULL
        AND NOT EXISTS (SELECT 1 FROM tenant t2 WHERE t2.parent_tenant_id = t.id);
    """)
    op.execute("ALTER TABLE tenant ALTER COLUMN tenant_type SET NOT NULL;")

    # updated_at trigger on tenant
    op.execute("DROP TRIGGER IF EXISTS trg_tenant__updated_at ON tenant;")
    op.execute("""
      CREATE TRIGGER trg_tenant__updated_at
      BEFORE UPDATE ON tenant
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    # ---------- user (tenant-scoped) ----------
    # Add failed_login_attempts + last_login
    op.add_column("user", sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("user", sa.Column("last_login", sa.TIMESTAMP(timezone=True), nullable=True))

    # Attach triggers: updated_at + tenant_guard
    op.execute("DROP TRIGGER IF EXISTS trg_app_user__updated_at ON user;")
    op.execute("""
      CREATE TRIGGER trg_app_user__updated_at
      BEFORE UPDATE ON user
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_app_user__tenant_guard ON user;")
    op.execute("""
      CREATE TRIGGER trg_app_user__tenant_guard
      BEFORE INSERT OR UPDATE ON user
      FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
    """)

    # Ensure RLS and policy on user
    op.execute("ALTER TABLE user ENABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON user;")
    op.execute("""
      CREATE POLICY tenant_isolation ON user
      USING (tenant_id = jwt_tenant())
      WITH CHECK (tenant_id = jwt_tenant());
    """)

    # ---------- MEMBERSHIP (tenant-scoped) ----------
    op.execute("DROP TRIGGER IF EXISTS trg_membership__updated_at ON membership;")
    op.execute("""
      CREATE TRIGGER trg_membership__updated_at
      BEFORE UPDATE ON membership
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_membership__tenant_guard ON membership;")
    op.execute("""
      CREATE TRIGGER trg_membership__tenant_guard
      BEFORE INSERT OR UPDATE ON membership
      FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
    """)
    op.execute("ALTER TABLE membership ENABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON membership;")
    op.execute("""
      CREATE POLICY tenant_isolation ON membership
      USING (tenant_id = jwt_tenant())
      WITH CHECK (tenant_id = jwt_tenant());
    """)

    # ---------- PLAN ----------
    # Ensure slug column + unique index
    op.add_column("plan", sa.Column("slug", sa.String(length=128), nullable=True))
    op.execute("""
      UPDATE plan SET slug = LOWER(REPLACE(name,' ','-')) WHERE slug IS NULL;
    """)
    op.execute("""
      DO $$
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'uq_plan_slug'
        ) THEN
          ALTER TABLE plan ADD CONSTRAINT uq_plan_slug UNIQUE (slug);
        END IF;
      END$$;
    """)
    op.execute("ALTER TABLE plan ALTER COLUMN slug SET NOT NULL;")

    # ---------- TENANT_PLAN_SUBSCRIPTIONS (tenant-scoped) ----------
    # Enable RLS + policy + triggers
    op.execute("ALTER TABLE tenant_plan_subscriptions ENABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_plan_subscriptions;")
    op.execute("""
      CREATE POLICY tenant_isolation ON tenant_plan_subscriptions
      USING (tenant_id = jwt_tenant())
      WITH CHECK (tenant_id = jwt_tenant());
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_tps__updated_at ON tenant_plan_subscriptions;")
    op.execute("""
      CREATE TRIGGER trg_tps__updated_at
      BEFORE UPDATE ON tenant_plan_subscriptions
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_tps__tenant_guard ON tenant_plan_subscriptions;")
    op.execute("""
      CREATE TRIGGER trg_tps__tenant_guard
      BEFORE INSERT OR UPDATE ON tenant_plan_subscriptions
      FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
    """)

    # ---------- AUDIT LOG (append-only, tenant-scoped) ----------
    # Block UPDATE/DELETE
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log__block_mutation ON audit_log;")
    op.execute("""
    CREATE OR REPLACE FUNCTION audit_log_block_mutation() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'audit_log is append-only; % not allowed', TG_OP;
    END; $$;
    """)
    op.execute("""
      CREATE TRIGGER trg_audit_log__block_mutation
      BEFORE UPDATE OR DELETE ON audit_log
      FOR EACH ROW EXECUTE FUNCTION audit_log_block_mutation();
    """)
    # Keep tenant RLS + policy + tenant_guard
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_log;")
    op.execute("""
      CREATE POLICY tenant_isolation ON audit_log
      USING (tenant_id = jwt_tenant())
      WITH CHECK (tenant_id = jwt_tenant());
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log__tenant_guard ON audit_log;")
    op.execute("""
      CREATE TRIGGER trg_audit_log__tenant_guard
      BEFORE INSERT OR UPDATE ON audit_log
      FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
    """)

    # ---------- Optional seed: Platform Owner tenant (no user here for security) ----------
    op.execute("""
    DO $$
    DECLARE _id uuid := gen_random_uuid();
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM tenant WHERE tenant_type = 'PLATFORM_OWNER') THEN
        INSERT INTO tenant(id, name, tenant_type, parent_tenant_id, is_active, created_at, updated_at)
        VALUES (_id, 'Raydian Platform', 'PLATFORM_OWNER', NULL, true, NOW(), NOW());
      END IF;
    END$$;
    """)


def downgrade():
    # Cautious rollback (keep data-safe operations)
    # Remove audit block trigger
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log__block_mutation ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS audit_log_block_mutation();")

    # Drop triggers added
    for tbl, trg in [
        ("tenant", "trg_tenant__updated_at"),
        ("user", "trg_app_user__updated_at"),
        ("user", "trg_app_user__tenant_guard"),
        ("membership", "trg_membership__updated_at"),
        ("membership", "trg_membership__tenant_guard"),
        ("tenant_plan_subscriptions", "trg_tps__updated_at"),
        ("tenant_plan_subscriptions", "trg_tps__tenant_guard"),
        ("audit_log", "trg_audit_log__tenant_guard"),
    ]:
        op.execute(f"DROP TRIGGER IF EXISTS {trg} ON {tbl};")

    # Drop RLS policies we added (leave RLS state as-is)
    for tbl in ["user","membership","tenant_plan_subscriptions","audit_log"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {tbl};")

    # Columns
    with op.batch_alter_table("plan") as b:
        b.drop_constraint("uq_plan_slug", type_="unique")
        b.drop_column("slug")
    with op.batch_alter_table("user") as b:
        b.drop_column("failed_login_attempts")
        b.drop_column("last_login")
    with op.batch_alter_table("tenant") as b:
        b.drop_column("tenant_type")

    # Functions (leave jwt_tenant if other modules depend on it)
    op.execute("DROP FUNCTION IF EXISTS ensure_tenant_id();")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
    # keep jwt_tenant(); comment out next line if others need it
    # op.execute("DROP FUNCTION IF EXISTS jwt_tenant();")