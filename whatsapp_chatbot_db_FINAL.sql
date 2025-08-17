-- ====================================================================================
-- WhatsApp Chatbot Platform — Production SQL Pack (PostgreSQL 14+)
-- ====================================================================================
-- Re-run helpers (commented; use with care)
-- DROP SCHEMA public CASCADE; CREATE SCHEMA public;
-- ====================================================================================

-- 0) SETUP ---------------------------------------------------------------------------
BEGIN;

-- Extensions required by the platform (id, crypto, case-insensitive email, GIN helpers)
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Session GUC used by the app to pass tenant context (from JWT).
-- In production, your API layer should SET app.jwt_tenant = '<uuid-from-jwt>';
-- Dev/test stub function: jwt_tenant() reads that value, else returns NIL UUID.
CREATE OR REPLACE FUNCTION jwt_tenant() RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT COALESCE(NULLIF(current_setting('app.jwt_tenant', true), '')::uuid,
                  '00000000-0000-0000-0000-000000000000'::uuid)
$$;

COMMENT ON FUNCTION jwt_tenant() IS
'Returns current tenant UUID from GUC app.jwt_tenant. In production this is set from the JWT claim.';

COMMIT;

-- 1) ENUMS / DOMAINS -----------------------------------------------------------------
BEGIN;

-- Core lifecycles
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_status_enum') THEN
    CREATE TYPE message_status_enum AS ENUM ('QUEUED','SENT','DELIVERED','FAILED');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'session_status_enum') THEN
    CREATE TYPE session_status_enum AS ENUM ('CREATED','ACTIVE','EXPIRED');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_direction_enum') THEN
    CREATE TYPE message_direction_enum AS ENUM ('INBOUND','OUTBOUND');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversation_stage_enum') THEN
    CREATE TYPE conversation_stage_enum AS ENUM ('INITIATED','IN_PROGRESS','AWAITING_INPUT','COMPLETED','EXPIRED');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'industry_type_enum') THEN
    CREATE TYPE industry_type_enum AS ENUM ('HEALTHCARE','EDUCATION','GENERIC');
  END IF;

  -- Identity / Tenancy
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tenant_type_enum') THEN
    CREATE TYPE tenant_type_enum AS ENUM ('PLATFORM_OWNER','RESELLER','CLIENT');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_status_enum') THEN
    CREATE TYPE subscription_status_enum AS ENUM ('ACTIVE','PAST_DUE','SUSPENDED','CANCELLED');
  END IF;

  -- Notifications
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'template_type_enum') THEN
    CREATE TYPE template_type_enum AS ENUM ('APPOINTMENT_REMINDER','FEE_REMINDER','GENERAL','EMERGENCY');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'delivery_channel_enum') THEN
    CREATE TYPE delivery_channel_enum AS ENUM ('WHATSAPP','SMS','EMAIL');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notification_priority_enum') THEN
    CREATE TYPE notification_priority_enum AS ENUM ('LOW','NORMAL','HIGH','URGENT');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notification_status_enum') THEN
    CREATE TYPE notification_status_enum AS ENUM ('SCHEDULED','QUEUED','SENT','DELIVERED','FAILED','CANCELLED');
  END IF;

  -- Healthcare
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'appointment_status_enum') THEN
    CREATE TYPE appointment_status_enum AS ENUM ('SCHEDULED','CONFIRMED','CANCELLED','COMPLETED','NO_SHOW');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'confirmation_status_enum') THEN
    CREATE TYPE confirmation_status_enum AS ENUM ('PENDING','CONFIRMED','DECLINED');
  END IF;

  -- Education / Billing
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fee_status_enum') THEN
    CREATE TYPE fee_status_enum AS ENUM ('PENDING','PAID','OVERDUE');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fee_type_enum') THEN
    CREATE TYPE fee_type_enum AS ENUM ('TUITION','TRANSPORT','LIBRARY','EXAMINATION','MISCELLANEOUS');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_method_enum') THEN
    CREATE TYPE payment_method_enum AS ENUM ('CASH','BANK_TRANSFER','ONLINE','CHEQUE');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'config_type_enum') THEN
    CREATE TYPE config_type_enum AS ENUM ('GENERAL','WHITELABEL','INTEGRATION','RISK');
  END IF;
END$$;

COMMIT;

-- 2) TABLES (3NF) --------------------------------------------------------------------
BEGIN;

-- 2.1 Tenants (platform-scoped; not tenant_id-scoped)
CREATE TABLE IF NOT EXISTS tenants (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                   varchar(255) NOT NULL UNIQUE,
  tenant_type            tenant_type_enum NOT NULL,
  parent_tenant_id       uuid NULL REFERENCES tenants(id) ON DELETE SET NULL,
  subscription_plan      varchar(50) NOT NULL,
  subscription_status    subscription_status_enum NOT NULL DEFAULT 'ACTIVE',
  billing_email          citext NULL,
  is_active              boolean NOT NULL DEFAULT true,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE tenants IS 'Tenant registry. Platform-scoped.';
COMMENT ON COLUMN tenants.subscription_plan IS 'Plan code; billing handled upstream.';
COMMENT ON COLUMN tenants.billing_email IS 'Billing contact; case-insensitive (citext).';

CREATE INDEX IF NOT EXISTS ix_tenants__parent ON tenants(parent_tenant_id);
CREATE INDEX IF NOT EXISTS ix_tenants__type_active ON tenants(tenant_type, is_active);

-- 2.2 Users (tenant-scoped)
CREATE TABLE IF NOT EXISTS users (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  email                  citext NOT NULL,
  password_hash          text   NOT NULL,
  roles                  text[] NOT NULL,
  is_active              boolean NOT NULL DEFAULT true,
  is_verified            boolean NOT NULL DEFAULT false,
  failed_login_attempts  int     NOT NULL DEFAULT 0,
  last_login             timestamptz NULL,
  password_changed_at    timestamptz NOT NULL DEFAULT now(),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  deleted_at             timestamptz NULL,
  CONSTRAINT uq_users__tenant_email UNIQUE(tenant_id, email),
  CONSTRAINT chk_users__roles_nonempty CHECK (array_length(roles,1) > 0)
);

COMMENT ON TABLE users IS 'Tenant users and admins.';
COMMENT ON COLUMN users.password_hash IS 'Argon2/BCrypt hash.';

CREATE INDEX IF NOT EXISTS ix_users__tenant_active ON users(tenant_id, is_active);
CREATE INDEX IF NOT EXISTS ix_users__failed_attempts ON users(failed_login_attempts) WHERE failed_login_attempts > 0;

-- 2.3 WhatsApp Channels (tenant-scoped)
CREATE TABLE IF NOT EXISTS whatsapp_channels (
  id                               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                        uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  phone_number_id                  text NOT NULL UNIQUE,
  business_phone                   varchar(20) NOT NULL,
  access_token_ciphertext          text NOT NULL,
  webhook_verify_token_ciphertext  text NOT NULL,
  webhook_url                      text NOT NULL,
  rate_limit_per_second            int  NOT NULL DEFAULT 10,
  monthly_message_limit            int  NOT NULL DEFAULT 10000,
  current_month_usage              int  NOT NULL DEFAULT 0,
  is_active                        boolean NOT NULL DEFAULT true,
  last_webhook_received            timestamptz NULL,
  created_at                       timestamptz NOT NULL DEFAULT now(),
  updated_at                       timestamptz NOT NULL DEFAULT now(),
  deleted_at                       timestamptz NULL,
  CONSTRAINT uq_channels__tenant_business UNIQUE(tenant_id, business_phone),
  CONSTRAINT chk_channels__phone_e164 CHECK (business_phone ~ '^\+[1-9]\d{1,14}$')
);

COMMENT ON TABLE whatsapp_channels IS
'WhatsApp Business configuration per tenant. Sensitive fields are ciphertext; actual encryption managed by KMS/app layer.';
COMMENT ON COLUMN whatsapp_channels.access_token_ciphertext IS 'Envelope-encrypted (app/KMS).';
COMMENT ON COLUMN whatsapp_channels.webhook_verify_token_ciphertext IS 'Envelope-encrypted (app/KMS).';

CREATE INDEX IF NOT EXISTS ix_channels__tenant_active ON whatsapp_channels(tenant_id, is_active);
CREATE INDEX IF NOT EXISTS ix_channels__tenant_created ON whatsapp_channels(tenant_id, created_at DESC);

-- 2.4 Messages (tenant-scoped; partitioned monthly by created_at)
CREATE TABLE IF NOT EXISTS messages (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  channel_id           uuid NOT NULL REFERENCES whatsapp_channels(id) ON DELETE RESTRICT,
  whatsapp_message_id  text NULL,
  direction            message_direction_enum NOT NULL,
  from_phone           varchar(20) NOT NULL,
  to_phone             varchar(20) NOT NULL,
  content_jsonb        jsonb NOT NULL,
  content_hash         text  NOT NULL,
  message_type         varchar(32) NOT NULL,
  status               message_status_enum NOT NULL,
  error_code           varchar(50) NULL,
  retry_count          int NOT NULL DEFAULT 0,
  created_at           timestamptz NOT NULL DEFAULT now(),
  delivered_at         timestamptz NULL,
  status_updated_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT uq_messages__whatsapp_id UNIQUE(whatsapp_message_id),
  CONSTRAINT chk_messages__from_e164 CHECK (from_phone ~ '^\+[1-9]\d{1,14}$'),
  CONSTRAINT chk_messages__to_e164   CHECK (to_phone   ~ '^\+[1-9]\d{1,14}$'),
  CONSTRAINT fk_messages__tenant_match
    CHECK (tenant_id = (SELECT tenant_id FROM whatsapp_channels c WHERE c.id = channel_id))
) PARTITION BY RANGE (created_at);

COMMENT ON TABLE messages IS
'Operational transport for WhatsApp messages. No PHI should be stored here; use tokenized links/IDs only.';

-- Current month partition auto-create
DO $$
DECLARE
  part_name text := format('messages_y%sm%s', to_char(now(),'YYYY'), to_char(now(),'MM'));
  start_ts  timestamptz := date_trunc('month', now());
  end_ts    timestamptz := (date_trunc('month', now()) + interval '1 month');
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = part_name) THEN
    EXECUTE format($f$
      CREATE TABLE IF NOT EXISTS %I PARTITION OF messages
      FOR VALUES FROM (%L) TO (%L)$f$, part_name, start_ts, end_ts);
  END IF;
END$$;

-- Hot-path indexes
CREATE INDEX IF NOT EXISTS ix_messages__tenant_channel_from_created
  ON messages (tenant_id, channel_id, from_phone, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_messages__tenant_created
  ON messages (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_messages__content_gin
  ON messages USING GIN (content_jsonb jsonb_path_ops);
CREATE INDEX IF NOT EXISTS ix_messages__content_hash ON messages(content_hash);
CREATE INDEX IF NOT EXISTS ix_messages__non_delivered
  ON messages(channel_id, status) WHERE status <> 'DELIVERED';
CREATE INDEX IF NOT EXISTS ix_messages__failed_retries
  ON messages(channel_id, status, retry_count)
  WHERE status = 'FAILED' AND retry_count < 3;

-- 2.5 Conversation Sessions (tenant-scoped)
CREATE TABLE IF NOT EXISTS conversation_sessions (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  channel_id           uuid NOT NULL REFERENCES whatsapp_channels(id) ON DELETE RESTRICT,
  phone_number         varchar(20) NOT NULL,
  current_menu_id      uuid NULL,
  context_jsonb        jsonb NOT NULL DEFAULT '{}',
  conversation_stage   conversation_stage_enum NOT NULL DEFAULT 'INITIATED',
  status               session_status_enum NOT NULL DEFAULT 'CREATED',
  message_count        int NOT NULL DEFAULT 0,
  created_at           timestamptz NOT NULL DEFAULT now(),
  expires_at           timestamptz NOT NULL,
  last_activity        timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT uq_sessions__channel_phone UNIQUE(channel_id, phone_number),
  CONSTRAINT chk_sessions__ttl CHECK (expires_at > created_at),
  CONSTRAINT chk_sessions__phone_e164 CHECK (phone_number ~ '^\+[1-9]\d{1,14}$'),
  CONSTRAINT fk_sessions__tenant_match
    CHECK (tenant_id = (SELECT tenant_id FROM whatsapp_channels c WHERE c.id = channel_id))
);

CREATE INDEX IF NOT EXISTS ix_sessions__tenant_phone_created
  ON conversation_sessions(tenant_id, phone_number, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_sessions__expires_at
  ON conversation_sessions(expires_at) WHERE expires_at < now();
CREATE INDEX IF NOT EXISTS ix_sessions__stage_last_activity
  ON conversation_sessions(conversation_stage, last_activity);

-- 2.6 Menu Flows (tenant-scoped)
CREATE TABLE IF NOT EXISTS menu_flows (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  industry_type        industry_type_enum NOT NULL,
  name                 varchar(255) NOT NULL,
  definition_jsonb     jsonb NOT NULL,
  version              int NOT NULL DEFAULT 1,
  is_active            boolean NOT NULL DEFAULT true,
  is_default           boolean NOT NULL DEFAULT false,
  created_by           uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT uq_flows__tenant_name_version UNIQUE(tenant_id, name, version),
  CONSTRAINT uq_flows__tenant_industry_default UNIQUE(tenant_id, industry_type, is_default)
    DEFERRABLE INITIALLY DEFERRED
);

-- 2.7 Healthcare: Patients, Doctors, Appointments (tenant-scoped)
CREATE TABLE IF NOT EXISTS patients (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  phone_number         varchar(20) NOT NULL,
  first_name           varchar(100) NOT NULL,
  last_name            varchar(100) NOT NULL,
  medical_id           varchar(50) NULL,
  date_of_birth        date NULL,
  emergency_contact    varchar(20) NULL,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT uq_patients__tenant_phone UNIQUE(tenant_id, phone_number),
  CONSTRAINT chk_patients__phone_e164 CHECK (phone_number ~ '^\+[1-9]\d{1,14}$')
);

CREATE TABLE IF NOT EXISTS doctors (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  first_name           varchar(100) NOT NULL,
  last_name            varchar(100) NOT NULL,
  specialization       varchar(100) NOT NULL,
  availability_schedule jsonb NOT NULL,
  consultation_duration int NOT NULL DEFAULT 30,
  is_active            boolean NOT NULL DEFAULT true,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT chk_doctors__duration_positive CHECK (consultation_duration > 0)
);

CREATE TABLE IF NOT EXISTS appointments (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  patient_id           uuid NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
  doctor_id            uuid NOT NULL REFERENCES doctors(id) ON DELETE RESTRICT,
  service_type         varchar(100) NOT NULL,
  scheduled_at         timestamptz NOT NULL,
  duration_minutes     int NOT NULL DEFAULT 30,
  status               appointment_status_enum NOT NULL DEFAULT 'SCHEDULED',
  confirmation_status  confirmation_status_enum NOT NULL DEFAULT 'PENDING',
  queue_position       int NULL,
  appointment_fee      numeric(10,2) NULL,
  notes                text NULL,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT chk_appointments__duration CHECK (duration_minutes > 0),
  CONSTRAINT chk_appointments__future CHECK (scheduled_at > now()),
  CONSTRAINT fk_appointments__tenant_match
    CHECK (tenant_id = (SELECT tenant_id FROM patients p WHERE p.id = patient_id)
       AND tenant_id = (SELECT tenant_id FROM doctors  d WHERE d.id = doctor_id))
);

CREATE INDEX IF NOT EXISTS ix_appt__patient_scheduled ON appointments(patient_id, scheduled_at DESC);
CREATE INDEX IF NOT EXISTS ix_appt__doctor_scheduled  ON appointments(doctor_id, scheduled_at);
CREATE INDEX IF NOT EXISTS ix_appt__tenant_status_date ON appointments(tenant_id, status, scheduled_at);

-- 2.8 Education: Students, Fee Records (tenant-scoped)
CREATE TABLE IF NOT EXISTS students (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  phone_number         varchar(20) NOT NULL,
  first_name           varchar(100) NOT NULL,
  last_name            varchar(100) NOT NULL,
  student_id_number    varchar(50) NOT NULL,
  class_grade          varchar(20) NOT NULL,
  parent_contact       varchar(20) NULL,
  enrollment_date      date NOT NULL,
  is_active            boolean NOT NULL DEFAULT true,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT uq_students__tenant_phone UNIQUE(tenant_id, phone_number),
  CONSTRAINT uq_students__tenant_sid UNIQUE(tenant_id, student_id_number)
);

CREATE TABLE IF NOT EXISTS fee_records (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  student_id           uuid NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
  academic_year        varchar(10) NOT NULL,
  fee_type             fee_type_enum NOT NULL,
  amount               numeric(10,2) NOT NULL,
  due_date             date NOT NULL,
  paid_date            date NULL,
  paid_amount          numeric(10,2) NOT NULL DEFAULT 0,
  payment_method       payment_method_enum NULL,
  late_fee             numeric(10,2) NOT NULL DEFAULT 0,
  status               fee_status_enum NOT NULL DEFAULT 'PENDING',
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT chk_fee__nonneg CHECK (amount >= 0 AND paid_amount >= 0 AND late_fee >= 0),
  CONSTRAINT fk_fee__tenant_match
    CHECK (tenant_id = (SELECT tenant_id FROM students s WHERE s.id = student_id))
);

CREATE INDEX IF NOT EXISTS ix_fee__student_year ON fee_records(student_id, academic_year DESC);
CREATE INDEX IF NOT EXISTS ix_fee__due_status ON fee_records(due_date, status) WHERE status IN ('PENDING','OVERDUE');
CREATE INDEX IF NOT EXISTS ix_fee__tenant_status_due ON fee_records(tenant_id, status, due_date);

-- 2.9 Notification Templates & Notifications (tenant-scoped)
CREATE TABLE IF NOT EXISTS notification_templates (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  name                 varchar(255) NOT NULL,
  template_type        template_type_enum NOT NULL,
  content_template     text NOT NULL,
  variables            jsonb NOT NULL DEFAULT '[]',
  delivery_channels    delivery_channel_enum[] NOT NULL,
  is_active            boolean NOT NULL DEFAULT true,
  created_by           uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT uq_tpl__tenant_name UNIQUE(tenant_id, name),
  CONSTRAINT chk_tpl__channels_nonempty CHECK (array_length(delivery_channels,1) > 0)
);

CREATE TABLE IF NOT EXISTS notifications (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  template_id          uuid NULL REFERENCES notification_templates(id) ON DELETE SET NULL,
  recipient_phone      varchar(20) NOT NULL,
  scheduled_at         timestamptz NOT NULL,
  priority             notification_priority_enum NOT NULL DEFAULT 'NORMAL',
  delivery_attempts    int NOT NULL DEFAULT 0,
  max_retry_attempts   int NOT NULL DEFAULT 3,
  status               notification_status_enum NOT NULL DEFAULT 'SCHEDULED',
  error_message        text NULL,
  context_jsonb        jsonb NOT NULL DEFAULT '{}',
  created_at           timestamptz NOT NULL DEFAULT now(),
  delivered_at         timestamptz NULL,
  deleted_at           timestamptz NULL,
  CONSTRAINT chk_notifications__attempts CHECK (delivery_attempts >= 0 AND max_retry_attempts >= 0),
  CONSTRAINT chk_notifications__phone_e164 CHECK (recipient_phone ~ '^\+[1-9]\d{1,14}$')
);

CREATE INDEX IF NOT EXISTS ix_notifications__queue
  ON notifications(scheduled_at, status, priority);
CREATE INDEX IF NOT EXISTS ix_notifications__tenant_status_created
  ON notifications(tenant_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_notifications__recipient_recent
  ON notifications(recipient_phone, created_at DESC);

-- 2.10 Tenant Configurations (tenant-scoped)
CREATE TABLE IF NOT EXISTS tenant_configurations (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id            uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  config_key           varchar(100) NOT NULL,
  config_value         jsonb NOT NULL,
  config_type          config_type_enum NOT NULL DEFAULT 'GENERAL',
  is_encrypted         boolean NOT NULL DEFAULT false,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  deleted_at           timestamptz NULL,
  CONSTRAINT uq_config__tenant_key UNIQUE(tenant_id, config_key)
);

COMMENT ON COLUMN tenant_configurations.config_value IS
'If is_encrypted=true, value holds ciphertext; KMS decryption at app layer.';

-- 2.11 Transactional Outbox (tenant-scoped)
CREATE TABLE IF NOT EXISTS outbox_events (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  aggregate_type text NOT NULL,
  aggregate_id   uuid NOT NULL,
  event_type     text NOT NULL,
  payload_jsonb  jsonb NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  processed_at   timestamptz NULL
);

CREATE INDEX IF NOT EXISTS ix_outbox__tenant_created ON outbox_events(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS ix_outbox__unprocessed ON outbox_events(tenant_id, processed_at) WHERE processed_at IS NULL;

-- 2.12 Idempotency (tenant-scoped, optional but recommended)
CREATE TABLE IF NOT EXISTS idempotency_keys (
  tenant_id      uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  endpoint       text NOT NULL,
  key            text NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  expires_at     timestamptz NOT NULL DEFAULT (now() + interval '24 hours'),
  PRIMARY KEY (tenant_id, endpoint, key)
);

CREATE INDEX IF NOT EXISTS ix_idem__expiry ON idempotency_keys(expires_at);

COMMIT;

-- 3) COMMON TRIGGER FUNCTIONS --------------------------------------------------------
BEGIN;

-- Updated_at management
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END$$;

-- Enforce / auto-fill tenant_id = jwt_tenant() on tenant-scoped tables
CREATE OR REPLACE FUNCTION ensure_tenant_id() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.tenant_id IS NULL THEN
      NEW.tenant_id := jwt_tenant();
    END IF;
    IF NEW.tenant_id <> jwt_tenant() THEN
      RAISE EXCEPTION 'tenant_id mismatch with jwt_tenant()';
    END IF;
  ELSIF TG_OP = 'UPDATE' THEN
    IF NEW.tenant_id <> OLD.tenant_id THEN
      RAISE EXCEPTION 'tenant_id cannot be changed';
    END IF;
    IF NEW.tenant_id <> jwt_tenant() THEN
      RAISE EXCEPTION 'tenant_id mismatch with jwt_tenant()';
    END IF;
  END IF;
  RETURN NEW;
END$$;

-- Reject content that looks like PHI in WhatsApp transport messages (policy stub).
CREATE OR REPLACE FUNCTION enforce_no_phi_in_whatsapp() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  forbidden_keys text[] := ARRAY['patient_name','dob','medical_id','mrn','ssn','address'];
BEGIN
  -- If message content includes suspicious keys, block (app should tokenize/de-identify)
  IF (SELECT bool_or(k = ANY(forbidden_keys))
        FROM jsonb_object_keys(NEW.content_jsonb) AS k) THEN
    RAISE EXCEPTION 'PHI-like fields not allowed in messages.content_jsonb';
  END IF;
  RETURN NEW;
END$$;

-- Write to outbox after aggregate mutations
CREATE OR REPLACE FUNCTION write_outbox_event() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  payload jsonb;
  agg_type text := TG_ARGV[0];
  ev_type  text := TG_ARGV[1];
  agg_id   uuid;
  ten_id   uuid;
BEGIN
  IF TG_OP IN ('INSERT','UPDATE') THEN
    payload := to_jsonb(NEW);
    ten_id  := NEW.tenant_id;
    IF NEW ? 'id' THEN
      agg_id := NEW.id;
    ELSE
      -- fallback: some tables might use different PK name; try channel/session/messages
      agg_id := COALESCE(NEW.id, NULL);
    END IF;
  ELSE
    payload := to_jsonb(OLD);
    ten_id  := OLD.tenant_id;
    agg_id  := COALESCE(OLD.id, NULL);
  END IF;

  INSERT INTO outbox_events(tenant_id, aggregate_type, aggregate_id, event_type, payload_jsonb)
  VALUES (ten_id, agg_type, COALESCE(agg_id, gen_random_uuid()), ev_type, payload);

  RETURN COALESCE(NEW, OLD);
END$$;

-- Enforce/auto-set session TTL (30 min default) and transitions
CREATE OR REPLACE FUNCTION enforce_session_ttl() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.expires_at IS NULL THEN
      NEW.expires_at := now() + interval '30 minutes';
    END IF;
    NEW.status := 'ACTIVE';
  ELSIF TG_OP = 'UPDATE' THEN
    IF NEW.expires_at <= NEW.created_at THEN
      RAISE EXCEPTION 'expires_at must be > created_at';
    END IF;
  END IF;
  RETURN NEW;
END$$;

COMMIT;

-- 4) TRIGGERS ------------------------------------------------------------------------
BEGIN;

-- updated_at triggers
CREATE TRIGGER trg_users__updated_at            BEFORE UPDATE ON users               FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_channels__updated_at         BEFORE UPDATE ON whatsapp_channels   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_patients__updated_at         BEFORE UPDATE ON patients            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_doctors__updated_at          BEFORE UPDATE ON doctors             FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_appointments__updated_at     BEFORE UPDATE ON appointments        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_students__updated_at         BEFORE UPDATE ON students            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_fee_records__updated_at      BEFORE UPDATE ON fee_records         FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_menu_flows__updated_at       BEFORE UPDATE ON menu_flows          FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_notification_templates__updated_at BEFORE UPDATE ON notification_templates FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_notifications__updated_at    BEFORE UPDATE ON notifications       FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- tenant safety triggers
CREATE TRIGGER trg_users__tenant_guard              BEFORE INSERT OR UPDATE ON users               FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_channels__tenant_guard           BEFORE INSERT OR UPDATE ON whatsapp_channels   FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_messages__tenant_guard           BEFORE INSERT OR UPDATE ON messages            FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_sessions__tenant_guard           BEFORE INSERT OR UPDATE ON conversation_sessions FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_menu_flows__tenant_guard         BEFORE INSERT OR UPDATE ON menu_flows          FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_patients__tenant_guard           BEFORE INSERT OR UPDATE ON patients            FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_doctors__tenant_guard            BEFORE INSERT OR UPDATE ON doctors             FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_appointments__tenant_guard       BEFORE INSERT OR UPDATE ON appointments        FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_students__tenant_guard           BEFORE INSERT OR UPDATE ON students            FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_fee_records__tenant_guard        BEFORE INSERT OR UPDATE ON fee_records         FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_notification_templates__tenant_guard BEFORE INSERT OR UPDATE ON notification_templates FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_notifications__tenant_guard      BEFORE INSERT OR UPDATE ON notifications       FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_outbox__tenant_guard             BEFORE INSERT OR UPDATE ON outbox_events       FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();
CREATE TRIGGER trg_idem__tenant_guard               BEFORE INSERT OR UPDATE ON idempotency_keys    FOR EACH ROW EXECUTE FUNCTION ensure_tenant_id();

-- PHI enforcement on messages
CREATE TRIGGER trg_messages__no_phi BEFORE INSERT OR UPDATE ON messages
FOR EACH ROW EXECUTE FUNCTION enforce_no_phi_in_whatsapp();

-- Outbox event writers (after mutations)
CREATE TRIGGER trg_messages__outbox     AFTER INSERT OR UPDATE ON messages
FOR EACH ROW EXECUTE FUNCTION write_outbox_event('Message','MessageChanged');

CREATE TRIGGER trg_sessions__outbox     AFTER INSERT OR UPDATE ON conversation_sessions
FOR EACH ROW EXECUTE FUNCTION write_outbox_event('ConversationSession','SessionChanged');

CREATE TRIGGER trg_appointments__outbox AFTER INSERT OR UPDATE ON appointments
FOR EACH ROW EXECUTE FUNCTION write_outbox_event('Appointment','AppointmentChanged');

CREATE TRIGGER trg_notifications__outbox AFTER INSERT OR UPDATE ON notifications
FOR EACH ROW EXECUTE FUNCTION write_outbox_event('Notification','NotificationChanged');

-- Session TTL / state
CREATE TRIGGER trg_sessions__ttl BEFORE INSERT OR UPDATE ON conversation_sessions
FOR EACH ROW EXECUTE FUNCTION enforce_session_ttl();

COMMIT;

-- 5) ROW-LEVEL SECURITY (RLS) --------------------------------------------------------
BEGIN;

-- Helper to enable RLS + standard tenant policy
CREATE OR REPLACE PROCEDURE enable_tenant_rls(tbl regclass) LANGUAGE plpgsql AS $$
BEGIN
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', tbl);
  -- Drop existing policy if present to make script idempotent
  IF EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = split_part(tbl::text, '.', 2) AND policyname = 'tenant_isolation') THEN
    EXECUTE format('DROP POLICY tenant_isolation ON %s', tbl);
  END IF;
  EXECUTE format(
    'CREATE POLICY tenant_isolation ON %s USING (tenant_id = jwt_tenant()) WITH CHECK (tenant_id = jwt_tenant())',
    tbl
  );
END$$;

-- Apply to all tenant-scoped tables
CALL enable_tenant_rls('users');
CALL enable_tenant_rls('whatsapp_channels');
CALL enable_tenant_rls('messages');
CALL enable_tenant_rls('conversation_sessions');
CALL enable_tenant_rls('menu_flows');
CALL enable_tenant_rls('patients');
CALL enable_tenant_rls('doctors');
CALL enable_tenant_rls('appointments');
CALL enable_tenant_rls('students');
CALL enable_tenant_rls('fee_records');
CALL enable_tenant_rls('notification_templates');
CALL enable_tenant_rls('notifications');
CALL enable_tenant_rls('tenant_configurations');
CALL enable_tenant_rls('outbox_events');
CALL enable_tenant_rls('idempotency_keys');

COMMIT;

-- 6) VIEWS & MATERIALIZED VIEWS ------------------------------------------------------
BEGIN;

-- Recent messages per (tenant, channel) limited to last 50 by window function
CREATE OR REPLACE VIEW vw_recent_messages AS
SELECT *
FROM (
  SELECT
    m.*,
    row_number() OVER (PARTITION BY m.tenant_id, m.channel_id ORDER BY m.created_at DESC) AS rn
  FROM messages m
) t
WHERE t.rn <= 50;

COMMENT ON VIEW vw_recent_messages IS 'Last 50 messages per (tenant, channel) for dashboards.';

-- Conversation windows: last 20 messages correlated to active session window
CREATE OR REPLACE VIEW vw_conversation_windows AS
SELECT *
FROM (
  SELECT
    s.id AS session_id,
    m.*,
    row_number() OVER (PARTITION BY s.id ORDER BY m.created_at DESC) AS rn
  FROM conversation_sessions s
  JOIN messages m
    ON m.tenant_id = s.tenant_id
   AND m.channel_id = s.channel_id
   AND (m.from_phone = s.phone_number OR m.to_phone = s.phone_number)
   AND m.created_at BETWEEN s.created_at AND s.expires_at
) z
WHERE z.rn <= 20;

COMMENT ON VIEW vw_conversation_windows IS 'Window of recent messages inside each active session timebox.';

-- Daily message stats (MATERIALIZED) per tenant/day & status
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_message_stats AS
SELECT
  tenant_id,
  date_trunc('day', created_at)::date AS day,
  status,
  count(*) AS cnt
FROM messages
GROUP BY tenant_id, day, status;

CREATE INDEX IF NOT EXISTS ix_mv_msgstats__tenant_day ON mv_daily_message_stats(tenant_id, day);

-- Refresh helper
CREATE OR REPLACE PROCEDURE sp_refresh_daily_stats() LANGUAGE sql AS $$
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_message_stats;
$$;

COMMIT;

-- 7) STORED PROCEDURES / FUNCTIONS (Business Flows) ---------------------------------
BEGIN;

-- Idempotency guard: returns true if (tenant, endpoint, key) existed or inserts it
CREATE OR REPLACE FUNCTION ensure_idempotency(p_endpoint text, p_key text)
RETURNS boolean
LANGUAGE plpgsql AS $$
DECLARE
  v_exists boolean;
BEGIN
  IF p_key IS NULL OR p_key = '' THEN
    RETURN false; -- no-op; not idempotent
  END IF;
  SELECT true INTO v_exists
  FROM idempotency_keys
  WHERE tenant_id = jwt_tenant() AND endpoint = p_endpoint AND key = p_key;

  IF v_exists THEN
    RETURN true;
  END IF;

  INSERT INTO idempotency_keys(tenant_id, endpoint, key) VALUES (jwt_tenant(), p_endpoint, p_key);
  RETURN false;
END$$;

-- Validate legal status transitions for messages
CREATE OR REPLACE FUNCTION legal_message_transition(old_status message_status_enum, new_status message_status_enum)
RETURNS boolean
LANGUAGE sql AS $$
  SELECT CASE
    WHEN old_status IS NULL AND new_status IN ('QUEUED') THEN true
    WHEN old_status = 'QUEUED' AND new_status IN ('SENT','FAILED') THEN true
    WHEN old_status = 'SENT'   AND new_status IN ('DELIVERED','FAILED') THEN true
    WHEN old_status = 'DELIVERED' AND new_status IN ('FAILED') THEN true
    WHEN old_status = new_status THEN true
    ELSE false
  END
$$;

-- Send message: inserts queued message, optional idempotency
CREATE OR REPLACE FUNCTION sp_send_message(
    p_channel_id uuid,
    p_to_phone   varchar,
    p_message_type varchar,
    p_content jsonb,
    p_idempotency_key text DEFAULT NULL
) RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE
  v_msg_id uuid;
  v_tenant uuid;
BEGIN
  -- Idempotency (optional)
  IF p_idempotency_key IS NOT NULL AND ensure_idempotency('send_message', p_idempotency_key) THEN
    -- Return an existing message id if you store it; here we simply short-circuit
    RAISE NOTICE 'Idempotent call ignored (send_message/%).', p_idempotency_key;
    RETURN NULL;
  END IF;

  SELECT tenant_id INTO v_tenant FROM whatsapp_channels WHERE id = p_channel_id;
  IF v_tenant IS NULL THEN
    RAISE EXCEPTION 'Channel not found';
  END IF;

  INSERT INTO messages(
    tenant_id, channel_id, whatsapp_message_id, direction, from_phone, to_phone,
    content_jsonb, content_hash, message_type, status
  )
  VALUES (
    v_tenant, p_channel_id, NULL, 'OUTBOUND',
    (SELECT business_phone FROM whatsapp_channels WHERE id = p_channel_id),
    p_to_phone, p_content, encode(digest(coalesce(p_content::text,''), 'sha256'), 'hex'),
    p_message_type, 'QUEUED'
  )
  RETURNING id INTO v_msg_id;

  -- Outbox event written by trigger (MessageChanged)
  RETURN v_msg_id;
END$$;

-- Update message status with transition enforcement
CREATE OR REPLACE PROCEDURE sp_update_message_status(p_message_id uuid, p_new_status message_status_enum)
LANGUAGE plpgsql AS $$
DECLARE
  v_old message_status_enum;
BEGIN
  SELECT status INTO v_old FROM messages WHERE id = p_message_id FOR UPDATE;
  IF v_old IS NULL THEN
    RAISE EXCEPTION 'Message not found';
  END IF;

  IF NOT legal_message_transition(v_old, p_new_status) THEN
    RAISE EXCEPTION 'Illegal message status transition: % -> %', v_old, p_new_status;
  END IF;

  UPDATE messages
     SET status = p_new_status,
         status_updated_at = now(),
         delivered_at = CASE WHEN p_new_status = 'DELIVERED' THEN now() ELSE delivered_at END
   WHERE id = p_message_id;
  -- Trigger writes outbox
END$$;

-- Open/close conversation sessions
CREATE OR REPLACE FUNCTION sp_open_session(p_channel_id uuid, p_user_phone varchar)
RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE
  v_id uuid;
  v_tenant uuid;
BEGIN
  SELECT tenant_id INTO v_tenant FROM whatsapp_channels WHERE id = p_channel_id;
  IF v_tenant IS NULL THEN
    RAISE EXCEPTION 'Channel not found';
  END IF;

  -- Upsert single active by (channel, phone)
  INSERT INTO conversation_sessions(tenant_id, channel_id, phone_number, expires_at)
  VALUES (v_tenant, p_channel_id, p_user_phone, now() + interval '30 minutes')
  ON CONFLICT (channel_id, phone_number) DO UPDATE
    SET last_activity = now(),
        expires_at = GREATEST(conversation_sessions.expires_at, now() + interval '30 minutes'),
        status = 'ACTIVE'
  RETURNING id INTO v_id;

  RETURN v_id;
END$$;

CREATE OR REPLACE PROCEDURE sp_close_session(p_session_id uuid)
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE conversation_sessions
     SET status = 'EXPIRED',
         expires_at = LEAST(expires_at, now()),
         last_activity = now()
   WHERE id = p_session_id;
  -- Trigger writes outbox
END$$;

-- Healthcare: book appointment with simple overlap guard
CREATE OR REPLACE FUNCTION sp_book_appointment(
  p_patient_id uuid,
  p_doctor_id  uuid,
  p_service_type varchar,
  p_scheduled_at timestamptz,
  p_duration_minutes int DEFAULT 30
) RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE
  v_tenant uuid;
  v_id uuid;
  v_end timestamptz := p_scheduled_at + make_interval(mins => p_duration_minutes);
BEGIN
  SELECT tenant_id INTO v_tenant FROM patients WHERE id = p_patient_id;
  IF v_tenant IS NULL THEN
    RAISE EXCEPTION 'Patient not found';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM doctors WHERE id = p_doctor_id AND tenant_id = v_tenant AND is_active) THEN
    RAISE EXCEPTION 'Doctor not found or inactive';
  END IF;

  -- basic overlap check
  IF EXISTS (
      SELECT 1 FROM appointments
       WHERE tenant_id = v_tenant AND doctor_id = p_doctor_id
         AND status IN ('SCHEDULED','CONFIRMED')
         AND tstzrange(scheduled_at, scheduled_at + make_interval(mins => duration_minutes)) &&
             tstzrange(p_scheduled_at, v_end)
  ) THEN
    RAISE EXCEPTION 'Requested slot overlaps existing appointment';
  END IF;

  INSERT INTO appointments(tenant_id, patient_id, doctor_id, service_type, scheduled_at, duration_minutes)
  VALUES (v_tenant, p_patient_id, p_doctor_id, p_service_type, p_scheduled_at, p_duration_minutes)
  RETURNING id INTO v_id;

  RETURN v_id;
END$$;

COMMIT;

-- 8) RUNTIME MAINTENANCE UTILITIES ---------------------------------------------------
BEGIN;

-- Purge expired idempotency keys (call from cron/job)
CREATE OR REPLACE PROCEDURE sp_purge_idempotency(expire_before timestamptz DEFAULT now())
LANGUAGE sql AS $$
  DELETE FROM idempotency_keys WHERE expires_at <= expire_before;
$$;

-- Partition helper: create next month partition for messages
CREATE OR REPLACE PROCEDURE sp_create_next_month_partition()
LANGUAGE plpgsql AS $$
DECLARE
  start_ts timestamptz := date_trunc('month', now() + interval '1 month');
  end_ts   timestamptz := date_trunc('month', now() + interval '2 months');
  part_name text := format('messages_y%sm%s', to_char(start_ts,'YYYY'), to_char(start_ts,'MM'));
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = part_name) THEN
    EXECUTE format($f$
      CREATE TABLE IF NOT EXISTS %I PARTITION OF messages
      FOR VALUES FROM (%L) TO (%L)$f$, part_name, start_ts, end_ts);
  END IF;
END$$;

COMMIT;

-- 9) COMMENTS (documentation highlights) --------------------------------------------
BEGIN;

COMMENT ON TABLE whatsapp_channels IS
'WhatsApp channel config (per tenant). Tokens are ciphertext placeholders; encryption/decryption handled in app via KMS.';

COMMENT ON TABLE messages IS
'Transport layer for WhatsApp messages. Strictly no PHI—store only tokenized references. HIPAA stance: transport stores non-PHI metadata and opaque content with pre-tokenized payloads.';

COMMENT ON TABLE outbox_events IS
'Transactional outbox for reliable integration with external brokers/queues. Workers poll unprocessed rows under RLS.';

COMMENT ON VIEW vw_conversation_windows IS
'Convenience view for Conversation Engine prefetch; relies on session window correlation by (channel_id, phone_number, timestamps).';

COMMIT;

-- 10) SAMPLE FIXTURES (COMMENTED) ----------------------------------------------------
-- BEGIN;
-- INSERT INTO tenants(name, tenant_type, subscription_plan) VALUES ('Demo Clinic', 'CLIENT', 'premium') RETURNING id;
-- SELECT set_config('app.jwt_tenant', '<returned-tenant-id>', true);
-- INSERT INTO users(tenant_id, email, password_hash, roles) VALUES (jwt_tenant(), 'admin@demo.test', '<hash>', ARRAY['CLIENT_ADMIN']);
-- COMMIT;

-- ====================================================================================
-- End of SQL Pack
-- ====================================================================================


-- ============================================================================
-- #suggestion changes: Production-readiness patches merged on 2025-08-16 (IST)
-- Notes:
-- - All changes are idempotent (IF NOT EXISTS / guarded DO-blocks).
-- - Addresses: enum completeness, hot-path index, MV CONCURRENTLY requirement,
--   and explicit tenant scoping for views / MV reader.
-- ============================================================================

-- 1) Enums --------------------------------------------------------------------
-- #suggestion changes: Add 'READ' state to message_status_enum (if missing)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_enum e
    JOIN pg_type t ON t.oid = e.enumtypid
    WHERE t.typname = 'message_status_enum' AND e.enumlabel = 'READ'
  ) THEN
    ALTER TYPE message_status_enum ADD VALUE IF NOT EXISTS 'READ';
  END IF;
END$$;

-- #suggestion changes: Update legal transition helper to allow DELIVERED -> READ
CREATE OR REPLACE FUNCTION legal_message_transition(
  old_status message_status_enum,
  new_status message_status_enum
) RETURNS boolean
LANGUAGE sql AS $$
  SELECT CASE
    WHEN old_status IS NULL AND new_status IN ('QUEUED') THEN true
    WHEN old_status = 'QUEUED'    AND new_status IN ('SENT','FAILED') THEN true
    WHEN old_status = 'SENT'      AND new_status IN ('DELIVERED','FAILED') THEN true
    WHEN old_status = 'DELIVERED' AND new_status IN ('READ','FAILED') THEN true
    WHEN old_status = new_status THEN true
    ELSE false
  END
$$;

-- 2) Indexes ------------------------------------------------------------------
-- #suggestion changes: Add recipient-side hot-path index
CREATE INDEX IF NOT EXISTS ix_messages__tenant_channel_to_created
  ON messages (tenant_id, channel_id, to_phone, created_at DESC);

-- 3) Views / Materialized Views ----------------------------------------------
-- #suggestion changes: Make vw_recent_messages explicitly tenant-scoped
CREATE OR REPLACE VIEW vw_recent_messages AS
SELECT *
FROM (
  SELECT
    m.*,
    row_number() OVER (PARTITION BY m.tenant_id, m.channel_id ORDER BY m.created_at DESC) AS rn
  FROM messages m
) t
WHERE t.rn <= 50
  AND t.tenant_id = jwt_tenant();

COMMENT ON VIEW vw_recent_messages IS 'Last 50 messages per (tenant, channel); explicitly tenant-scoped.';

-- #suggestion changes: Make vw_conversation_windows explicitly tenant-scoped
CREATE OR REPLACE VIEW vw_conversation_windows AS
SELECT *
FROM (
  SELECT
    s.id AS session_id,
    m.*,
    row_number() OVER (PARTITION BY s.id ORDER BY m.created_at DESC) AS rn
  FROM conversation_sessions s
  JOIN messages m
    ON m.tenant_id = s.tenant_id
   AND m.channel_id = s.channel_id
   AND (m.from_phone = s.phone_number OR m.to_phone = s.phone_number)
   AND m.created_at BETWEEN s.created_at AND s.expires_at
) z
WHERE z.rn <= 20
  AND z.tenant_id = jwt_tenant();

COMMENT ON VIEW vw_conversation_windows IS 'Window of recent messages inside each active session; explicitly tenant-scoped.';

-- #suggestion changes: MV unique index required for REFRESH CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_daily_message_stats
  ON mv_daily_message_stats (tenant_id, day, status);

-- #suggestion changes: RLS-safe reader over MV; prefer granting SELECT on the view
CREATE OR REPLACE VIEW vw_daily_message_stats AS
SELECT *
FROM mv_daily_message_stats
WHERE tenant_id = jwt_tenant();

-- Optional privilege hardening (uncomment and tailor to your roles)
-- REVOKE ALL ON mv_daily_message_stats FROM PUBLIC;
-- GRANT SELECT ON vw_daily_message_stats TO PUBLIC; -- or a specific role

-- ============================================================================
-- End of #suggestion changes
-- ============================================================================
