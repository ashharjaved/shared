- db/migrations/0002_init_messages.sql
-- =====================================================

-- Stage-2 Messaging Schema Migration
-- Multi-tenant WhatsApp messaging with partitioning and RLS

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- ----------------------------------------------------
-- 1) Helper: legal_message_transition(old,new)
-- Centralized transition rules; usable by DB logic & workers
-- ------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc
    WHERE proname = 'legal_message_transition'
  ) THEN
    CREATE FUNCTION legal_message_transition(
      p_old message_status,
      p_new message_status
    ) RETURNS boolean
    LANGUAGE plpgsql
    AS $fn$
    BEGIN
      RETURN CASE
        WHEN p_old = 'QUEUED'   AND p_new = 'SENT'      THEN TRUE
        WHEN p_old = 'SENT'     AND p_new IN ('DELIVERED','FAILED') THEN TRUE
        WHEN p_old = 'DELIVERED'AND p_new = 'READ'      THEN TRUE
        WHEN p_old = 'FAILED'   AND p_new = 'QUEUED'    THEN TRUE  -- allow retry
        WHEN p_old = p_new THEN TRUE  -- idempotent repeats
        ELSE FALSE
      END;
    END;
    $fn$;
  END IF;
END$$;

-- Create ENUM types
CREATE TYPE message_direction AS ENUM ('INBOUND', 'OUTBOUND');
CREATE TYPE message_type AS ENUM ('TEXT', 'TEMPLATE', 'MEDIA');
CREATE TYPE message_status AS ENUM ('QUEUED', 'SENT', 'DELIVERED', 'READ', 'FAILED');

-- WhatsApp Channels Table
CREATE TABLE whatsapp_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    phone_number_id TEXT NOT NULL,
    business_phone TEXT NOT NULL,
    access_token TEXT NOT NULL,
    webhook_token TEXT NOT NULL,
    rate_limit_per_second INTEGER NOT NULL DEFAULT 10,
    monthly_message_limit INTEGER NOT NULL DEFAULT 100000,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_business_phone_e164 CHECK (business_phone ~ '^\+?[1-9]\d{6,14}$');
);

-- Messages parent table (for partitioning)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    channel_id UUID NOT NULL,
    whatsapp_message_id TEXT NULL,
    direction message_direction NOT NULL,
    from_phone TEXT NOT NULL,
    to_phone TEXT NOT NULL,
    content_jsonb JSONB NOT NULL,
    content_hash TEXT NOT NULL,
    message_type message_type NOT NULL,
    status message_status NOT NULL DEFAULT 'QUEUED',
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ NULL,
    CONSTRAINT fk_messages_channel FOREIGN KEY (channel_id, tenant_id) REFERENCES whatsapp_channels(id, tenant_id);
    CONSTRAINT chk_from_phone_e164 CHECK (from_phone ~ '^\+?[1-9]\d{6,14}$');
    CONSTRAINT chk_to_phone_e164 CHECK (to_phone ~ '^\+?[1-9]\d{6,14}$');
) PARTITION BY RANGE (created_at);

-- Create initial partitions for current and next month
CREATE TABLE messages_current PARTITION OF messages
    FOR VALUES FROM (date_trunc('month', CURRENT_DATE)) TO (date_trunc('month', CURRENT_DATE) + INTERVAL '1 month');

CREATE TABLE messages_next PARTITION OF messages
    FOR VALUES FROM (date_trunc('month', CURRENT_DATE) + INTERVAL '1 month') TO (date_trunc('month', CURRENT_DATE) + INTERVAL '2 months');

-- Indexes for whatsapp_channels
CREATE UNIQUE INDEX idx_whatsapp_channels_tenant_phone_number 
    ON whatsapp_channels (tenant_id, phone_number_id);
CREATE UNIQUE INDEX idx_whatsapp_channels_tenant_business_phone 
    ON whatsapp_channels (tenant_id, business_phone);
CREATE INDEX idx_whatsapp_channels_tenant_active 
    ON whatsapp_channels (tenant_id, is_active);

-- Indexes for messages (created on parent table, inherited by partitions)
CREATE INDEX ix_messages_tenant_created ON messages (tenant_id, created_at);
CREATE INDEX ix_messages_status ON messages (tenant_id, status, created_at DESC);
CREATE INDEX ix_messages_channel_phone ON messages (tenant_id, channel_id, to_phone, created_at DESC);
CREATE INDEX ix_messages_wa_id ON messages (tenant_id, whatsapp_message_id);
CREATE INDEX ix_messages_content_jsonb ON messages USING GIN (content_jsonb);


-- RLS Policies
CREATE POLICY tenant_isolation_whatsapp_channels ON whatsapp_channels
    USING (tenant_id = current_setting('app.jwt_tenant')::UUID);

CREATE POLICY tenant_isolation_messages ON messages
    USING (tenant_id = current_setting('app.jwt_tenant')::UUID);

ALTER TABLE whatsapp_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Triggers
CREATE OR REPLACE TRIGGER ensure_tenant_id_whatsapp_channels
    BEFORE INSERT OR UPDATE ON whatsapp_channels
    FOR EACH ROW
    EXECUTE FUNCTION ensure_tenant_id();

CREATE OR REPLACE TRIGGER set_updated_at_whatsapp_channels
    BEFORE UPDATE ON whatsapp_channels
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER ensure_tenant_id_messages
    BEFORE INSERT OR UPDATE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION ensure_tenant_id();

CREATE OR REPLACE TRIGGER set_updated_at_messages
    BEFORE UPDATE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER write_outbox_event_messages
    AFTER INSERT OR UPDATE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION write_outbox_event();

CREATE OR REPLACE TRIGGER enforce_no_phi_in_whatsapp
    BEFORE INSERT OR UPDATE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION enforce_no_phi_in_whatsapp();

-- Functions
CREATE OR REPLACE FUNCTION sp_create_next_month_partition()
RETURNS void AS $$
DECLARE
    next_month_start DATE;
    next_month_end DATE;
    partition_name TEXT;
    next_month_start_2 DATE;
    next_month_end_2 DATE;
    partition_name_2 TEXT;
BEGIN
    -- Create partition for next month
    next_month_start := date_trunc('month', CURRENT_DATE + INTERVAL '1 month');
    next_month_end := next_month_start + INTERVAL '1 month';
    partition_name := 'messages_' || to_char(next_month_start, 'YYYY_MM');
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE tablename = partition_name
    ) THEN
        EXECUTE format('
            CREATE TABLE %I PARTITION OF messages
            FOR VALUES FROM (%L) TO (%L)
        ', partition_name, next_month_start, next_month_end);
    END IF;

    -- Create partition for month after next
    next_month_start_2 := next_month_start + INTERVAL '1 month';
    next_month_end_2 := next_month_start_2 + INTERVAL '1 month';
    partition_name_2 := 'messages_' || to_char(next_month_start_2, 'YYYY_MM');
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE tablename = partition_name_2
    ) THEN
        EXECUTE format('
            CREATE TABLE %I PARTITION OF messages
            FOR VALUES FROM (%L) TO (%L)
        ', partition_name_2, next_month_start_2, next_month_end_2);
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION sp_send_message(
    p_channel_id UUID,
    p_to_phone TEXT,
    p_type TEXT,
    p_content JSONB,
    p_idempotency_key TEXT
)
RETURNS UUID AS $$
DECLARE
    v_tenant_id UUID;
    v_channel_tenant_id UUID;
    v_message_id UUID;
    v_canonical_content TEXT;
    v_content_hash TEXT;
BEGIN
    -- Validate E.164 format
    IF p_to_phone !~ '^\+?[1-9]\d{6,14}$' THEN
        RAISE EXCEPTION 'Invalid E.164 phone number format: %', p_to_phone;
    END IF;

    -- Validate message type
    IF p_type NOT IN ('TEXT', 'TEMPLATE', 'MEDIA') THEN
        RAISE EXCEPTION 'Invalid message type: %', p_type;
    END IF;

    -- Check idempotency
    PERFORM ensure_idempotency('send_message', p_idempotency_key);

    -- Get tenant context
    v_tenant_id := current_setting('app.jwt_tenant')::UUID;

    -- Verify channel belongs to tenant
    SELECT tenant_id INTO v_channel_tenant_id
    FROM whatsapp_channels 
    WHERE id = p_channel_id;

    IF v_channel_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Channel not found: %', p_channel_id;
    END IF;

    IF v_channel_tenant_id != v_tenant_id THEN
        RAISE EXCEPTION 'Channel does not belong to tenant';
    END IF;

    -- Canonicalize and hash content
    v_canonical_content := canonical_json(p_content);
    v_content_hash := encode(sha256(v_canonical_content::bytea), 'hex');

    -- Insert message
    INSERT INTO messages (
        tenant_id,
        channel_id,
        direction,
        from_phone,
        to_phone,
        content_jsonb,
        content_hash,
        message_type,
        status
    ) VALUES (
        v_tenant_id,
        p_channel_id,
        'OUTBOUND'::message_direction,
        (SELECT business_phone FROM whatsapp_channels WHERE id = p_channel_id),
        p_to_phone,
        p_content,
        v_content_hash,
        p_type::message_type,
        'QUEUED'
    )
    RETURNING id INTO v_message_id;

    RETURN v_message_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION sp_update_message_status(
    p_message_id UUID,
    p_new_status TEXT,
    p_error_code TEXT DEFAULT NULL
)
RETURNS void AS $$
DECLARE
    v_tenant_id UUID;
    v_current_status message_status;
    v_valid_transition BOOLEAN;
BEGIN
    -- Get tenant context
    v_tenant_id := current_setting('app.jwt_tenant')::UUID;

    -- Get current status
    SELECT status INTO v_current_status
    FROM messages 
    WHERE id = p_message_id AND tenant_id = v_tenant_id;

    IF v_current_status IS NULL THEN
        RAISE EXCEPTION 'Message not found: %', p_message_id;
    END IF;

    -- Validate status transition
    v_valid_transition := CASE 
        WHEN v_current_status = 'QUEUED' AND p_new_status = 'SENT' THEN TRUE
        WHEN v_current_status = 'SENT' AND p_new_status IN ('DELIVERED', 'FAILED') THEN TRUE
        WHEN v_current_status = 'DELIVERED' AND p_new_status = 'READ' THEN TRUE
        WHEN v_current_status = 'FAILED' AND p_new_status = 'QUEUED' THEN TRUE -- Allow retry
        ELSE FALSE
    END;

    IF NOT v_valid_transition THEN
        RAISE EXCEPTION 'Invalid status transition from % to %', v_current_status, p_new_status;
    END IF;

    -- Update message status
    UPDATE messages 
    SET 
        status = p_new_status::message_status,
        status_updated_at = NOW(),
        error_code = p_error_code,
        delivered_at = CASE 
            WHEN p_new_status = 'DELIVERED' THEN NOW() 
            ELSE delivered_at 
        END,
        retry_count = CASE 
            WHEN p_new_status = 'QUEUED' THEN retry_count + 1 
            ELSE retry_count 
        END
    WHERE id = p_message_id AND tenant_id = v_tenant_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Message update failed: %', p_message_id;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Schedule partition creation (run this monthly)
SELECT cron.schedule('create-message-partitions', '0 0 1 * *', 'SELECT sp_create_next_month_partition()');

-- Create initial partitions
SELECT sp_create_next_month_partition();

-- ------------------------------------------------------------
-- 2) Fast “recent per-channel” view for conversation context
-- Last 50 messages per (tenant,channel), RLS applies via base
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_recent_messages AS
SELECT sub.*
FROM (
  SELECT
    m.*,
    ROW_NUMBER() OVER (PARTITION BY m.tenant_id, m.channel_id ORDER BY m.created_at DESC) AS rn
  FROM messages m
) sub
WHERE sub.rn <= 50;

-- ------------------------------------------------------------
-- 3) Conversation window view (only if Stage-4 table exists)
-- Joins messages within each active session’s time window.
-- Will only be created when conversation_sessions is present.
-- ------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.conversation_sessions') IS NOT NULL THEN
    EXECUTE $sql$
      CREATE OR REPLACE VIEW vw_conversation_windows AS
      SELECT
        s.id AS session_id,
        s.tenant_id,
        s.channel_id,
        s.phone_number,
        m.*
      FROM conversation_sessions s
      JOIN messages m
        ON m.tenant_id = s.tenant_id
       AND m.channel_id = s.channel_id
       AND (m.from_phone = s.phone_number OR m.to_phone = s.phone_number)
       AND m.created_at BETWEEN s.created_at AND s.expires_at
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY s.id
        ORDER BY m.created_at DESC
      ) <= 20;
    $sql$;
  END IF;
END$$;

-- ------------------------------------------------------------
-- 4) Daily analytics MV + refresh function + schedule
-- Counts per day with status breakdown; supports dashboards
-- ------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.mv_daily_message_stats') IS NULL THEN
    EXECUTE $sql$
      CREATE MATERIALIZED VIEW mv_daily_message_stats AS
      SELECT
        tenant_id,
        channel_id,
        date_trunc('day', created_at)::date AS day,
        COUNT(*)                                              AS total,
        COUNT(*) FILTER (WHERE direction = 'OUTBOUND')        AS total_outbound,
        COUNT(*) FILTER (WHERE direction = 'INBOUND')         AS total_inbound,
        COUNT(*) FILTER (WHERE status = 'QUEUED')             AS queued,
        COUNT(*) FILTER (WHERE status = 'SENT')               AS sent,
        COUNT(*) FILTER (WHERE status = 'DELIVERED')          AS delivered,
        COUNT(*) FILTER (WHERE status = 'READ')               AS read,
        COUNT(*) FILTER (WHERE status = 'FAILED')             AS failed
      FROM messages
      GROUP BY 1,2,3
      WITH NO DATA;
    $sql$;

    -- Unique index required for CONCURRENT refresh
    EXECUTE 'CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_daily_message_stats ON mv_daily_message_stats (tenant_id, channel_id, day)';
  END IF;
END$$;

CREATE OR REPLACE FUNCTION sp_refresh_daily_stats()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_message_stats;
END;
$$;

-- Nightly refresh @00:05
SELECT cron.schedule(
  'refresh-daily-message-stats',
  '5 0 * * *',
  'SELECT sp_refresh_daily_stats()'
)
ON CONFLICT DO NOTHING;

-- ------------------------------------------------------------
-- 5) Monthly usage helper (enforces monthly_message_limit)
-- Counts OUTBOUND messages in current calendar month.
-- ------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc WHERE proname='count_messages_sent_this_month'
  ) THEN
    CREATE FUNCTION count_messages_sent_this_month(p_tenant_id UUID)
    RETURNS BIGINT
    LANGUAGE sql
    STABLE
    AS $fn$
      SELECT COUNT(*)::bigint
      FROM messages
      WHERE tenant_id = p_tenant_id
        AND direction = 'OUTBOUND'
        AND status IN ('SENT','DELIVERED','READ')
        AND created_at >= date_trunc('month', now())
        AND created_at <  date_trunc('month', now()) + INTERVAL '1 month';
    $fn$;
  END IF;
END$$;

-- ------------------------------------------------------------
-- 6) Webhook raw event storage (optional but recommended)
-- Keeps provider payloads for audit/debug; RLS + tenant guard
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS webhook_events (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    UUID NOT NULL REFERENCES tenants(id),
  channel_id   UUID NOT NULL,
  provider     TEXT NOT NULL DEFAULT 'whatsapp',
  event_type   TEXT NULL,
  payload      JSONB NOT NULL,
  received_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Composite FK to ensure tenant-safe channel
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_webhook_events_channel'
  ) THEN
    ALTER TABLE webhook_events
      ADD CONSTRAINT fk_webhook_events_channel
      FOREIGN KEY (channel_id, tenant_id)
      REFERENCES whatsapp_channels(id, tenant_id);
  END IF;
END $$;

-- RLS & triggers
ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE polname='tenant_isolation_webhook_events') THEN
    CREATE POLICY tenant_isolation_webhook_events ON webhook_events
      USING (tenant_id = current_setting('app.jwt_tenant')::uuid);
  END IF;
END $$;

CREATE OR REPLACE TRIGGER ensure_tenant_id_webhook_events
  BEFORE INSERT OR UPDATE ON webhook_events
  FOR EACH ROW
  EXECUTE FUNCTION ensure_tenant_id();

  CREATE OR REPLACE TRIGGER set_updated_at_webhook_events
  BEFORE UPDATE ON webhook_events
  FOR EACH ROW
  EXECUTE FUNCTION set_updated_at();

-- ------------------------------------------------------------
-- 7) Inbound message processor (creates INBOUND messages)
-- Normalizes content, hashes payload, writes outbox via trigger
-- ------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc WHERE proname='sp_process_inbound_message'
  ) THEN
    CREATE FUNCTION sp_process_inbound_message(
      p_channel_id UUID,
      p_from_phone TEXT,
      p_to_phone   TEXT DEFAULT NULL,
      p_message_type TEXT DEFAULT 'TEXT',
      p_content    JSONB,
      p_whatsapp_message_id TEXT DEFAULT NULL
    )
    RETURNS UUID
    LANGUAGE plpgsql
    SECURITY DEFINER
    AS $fn$
    DECLARE
      v_tenant UUID := current_setting('app.jwt_tenant')::uuid;
      v_channel_phone TEXT;
      v_canonical JSONB;
      v_hash TEXT;
      v_id UUID;
    BEGIN
      -- ensure channel belongs to tenant
      PERFORM 1 FROM whatsapp_channels
       WHERE id = p_channel_id
         AND tenant_id = v_tenant;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'Channel % not found for tenant %', p_channel_id, v_tenant;
      END IF;

      -- default to channel business phone if not provided
      IF p_to_phone IS NULL THEN
        SELECT business_phone INTO v_channel_phone
        FROM whatsapp_channels
        WHERE id = p_channel_id;
      ELSE
        v_channel_phone := p_to_phone;
      END IF;

      v_canonical := canonical_json(p_content);
      v_hash := encode(sha256(v_canonical::bytea), 'hex');

      INSERT INTO messages(
        tenant_id, channel_id, whatsapp_message_id,
        direction, from_phone, to_phone,
        content_jsonb, content_hash,
        message_type, status
      ) VALUES (
        v_tenant, p_channel_id, p_whatsapp_message_id,
        'INBOUND', p_from_phone, v_channel_phone,
        v_canonical, v_hash,
        p_message_type::message_type, 'DELIVERED'
      )
      RETURNING id INTO v_id;

      RETURN v_id;
    END;
    $fn$;
  END IF;
END$$;

-- ------------------------------------------------------------
-- 8) Retry/DLQ helpers
-- View for backoff candidates, and DLQ table + mover function
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_messages_retry_candidates AS
SELECT m.*
FROM messages m
WHERE m.status = 'FAILED'
  AND m.retry_count < 5
  AND (now() - m.status_updated_at) >= (INTERVAL '10 seconds' * (POWER(2, m.retry_count)::int));

CREATE TABLE IF NOT EXISTS message_send_dlq (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    UUID NOT NULL REFERENCES tenants(id),
  message_id   UUID NOT NULL,
  reason       TEXT,
  payload      JSONB,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_message_send_dlq_message'
  ) THEN
    ALTER TABLE message_send_dlq
      ADD CONSTRAINT fk_message_send_dlq_message
      FOREIGN KEY (message_id) REFERENCES messages(id);
  END IF;
END $$;

ALTER TABLE message_send_dlq ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE polname='tenant_isolation_message_send_dlq') THEN
    CREATE POLICY tenant_isolation_message_send_dlq ON message_send_dlq
      USING (tenant_id = current_setting('app.jwt_tenant')::uuid);
  END IF;
END $$;

CREATE OR REPLACE TRIGGER ensure_tenant_id_message_send_dlq
  BEFORE INSERT OR UPDATE ON message_send_dlq
  FOR EACH ROW
  EXECUTE FUNCTION ensure_tenant_id();

CREATE OR REPLACE FUNCTION sp_move_to_dlq(p_message_id UUID, p_reason TEXT)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_tenant UUID := current_setting('app.jwt_tenant')::uuid;
  v_row messages%ROWTYPE;
BEGIN
  SELECT * INTO v_row FROM messages WHERE id = p_message_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Message not found: %', p_message_id;
  END IF;

  INSERT INTO message_send_dlq(tenant_id, message_id, reason, payload)
  VALUES (v_tenant, p_message_id, p_reason, to_jsonb(v_row));

  -- Leave message as FAILED; worker decides whether to delete/update
END;
$$;

-- ------------------------------------------------------------
-- 9) Index hardening (lookup by WA id & queue scans)
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_messages_wa_id_only ON messages (whatsapp_message_id) WHERE whatsapp_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_messages_failed_retry ON messages (status, retry_count, status_updated_at);

-- ------------------------------------------------------------
-- 10) (Optional) Security hardening for tokens at rest
-- Adds a marker flag; actual crypto handled in application layer.
-- ------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='whatsapp_channels' AND column_name='is_encrypted'
  ) THEN
    ALTER TABLE whatsapp_channels
    ADD COLUMN is_encrypted BOOLEAN NOT NULL DEFAULT FALSE;
  END IF;
END$$;

COMMENT ON COLUMN whatsapp_channels.access_token IS
  'Store ciphertext only. Encrypt/decrypt in app (AES-256 envelope/KMS).';
COMMENT ON COLUMN whatsapp_channels.webhook_token IS
  'If stored, store ciphertext. Prefer env-configured verify token.';
COMMENT ON COLUMN whatsapp_channels.is_encrypted IS
  'Indicates sensitive fields are encrypted by application before persistence.';

-- Grant permissions (adjust based on your security model)
GRANT SELECT, INSERT, UPDATE ON whatsapp_channels TO authenticated_user;
GRANT SELECT, INSERT, UPDATE ON messages TO authenticated_user;
GRANT EXECUTE ON FUNCTION sp_send_message TO authenticated_user;
GRANT EXECUTE ON FUNCTION sp_update_message_status TO authenticated_user;
GRANT INSERT, SELECT ON webhook_events TO authenticated_user;
GRANT EXECUTE ON FUNCTION sp_process_inbound_message(UUID, TEXT, TEXT, TEXT, JSONB, TEXT) TO authenticated_user;
GRANT SELECT ON vw_messages_retry_candidates TO authenticated_user;
GRANT SELECT, INSERT ON message_send_dlq TO authenticated_user;
GRANT EXECUTE ON FUNCTION sp_move_to_dlq(UUID, TEXT) TO authenticated_user;