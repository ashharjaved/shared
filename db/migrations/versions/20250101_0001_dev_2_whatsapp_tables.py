# # Alembic migration script
# # src/migrations/versions/20250101_0001_dev_2_whatsapp_tables.py
# """Dev-2 WhatsApp tables migration

# Revision ID: 20250101_0001
# Revises: 
# Create Date: 2025-01-01 00:00:00.000000
# """

# from alembic import op
# import sqlalchemy as sa
# from sqlalchemy.dialects import postgresql

# # revision identifiers, used by Alembic.
# revision = '20250101_0001'
# down_revision = None
# branch_labels = None
# depends_on = None

# def upgrade():
#     # Create wa_channel table
#     op.create_table(
#         'wa_channel',
#         sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column('phone_number_id', sa.String(), nullable=False),
#         sa.Column('waba_id', sa.String(), nullable=False),
#         sa.Column('display_name', sa.String(), nullable=True),
#         sa.Column('status', sa.String(), nullable=False, server_default='active'),
#         sa.Column('credentials', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
#         sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
#         sa.PrimaryKeyConstraint('id'),
#         sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE')
#     )
#     op.create_index('wa_channel_tenant_idx', 'wa_channel', ['tenant_id'])
    
#     # Create message table (will be partitioned monthly)
#     op.create_table(
#         'message',
#         sa.Column('id', sa.BigInteger(), nullable=False),
#         sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column('wa_message_id', sa.String(), nullable=True),
#         sa.Column('direction', sa.String(), nullable=False),
#         sa.Column('from_msisdn', sa.String(), nullable=False),
#         sa.Column('to_msisdn', sa.String(), nullable=False),
#         sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
#         sa.Column('template_name', sa.String(), nullable=True),
#         sa.Column('status', sa.String(), nullable=False, server_default='queued'),
#         sa.Column('error_code', sa.String(), nullable=True),
#         sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
#         sa.PrimaryKeyConstraint('id', 'created_at'),
#         sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
#         sa.ForeignKeyConstraint(['channel_id'], ['wa_channel.id'], ondelete='CASCADE'),
#         postgresql_partition_by='RANGE (created_at)'
#     )
#     op.create_index('message_waid_idx', 'message', ['wa_message_id'])
    
#     # Create outbox table
#     op.create_table(
#         'outbox',
#         sa.Column('id', sa.BigInteger(), nullable=False),
#         sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
#         sa.Column('kind', sa.String(), nullable=False),
#         sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
#         sa.Column('dedupe_key', sa.String(), nullable=True),
#         sa.Column('available_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
#         sa.Column('attempt', sa.Integer(), nullable=False, server_default='0'),
#         sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='12'),
#         sa.Column('last_error', sa.Text(), nullable=True),
#         sa.Column('claimed_by', sa.String(), nullable=True),
#         sa.Column('claimed_at', sa.DateTime(), nullable=True),
#         sa.PrimaryKeyConstraint('id'),
#         sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
#         sa.ForeignKeyConstraint(['channel_id'], ['wa_channel.id'], ondelete='CASCADE'),
#         sa.UniqueConstraint('dedupe_key', name='uq_outbox_dedupe_key')
#     )
#     op.create_index('outbox_avail_idx', 'outbox', ['available_at'])
    
#     # Enable RLS on all tables
#     op.execute('ALTER TABLE wa_channel ENABLE ROW LEVEL SECURITY')
#     op.execute('ALTER TABLE message ENABLE ROW LEVEL SECURITY')
#     op.execute('ALTER TABLE outbox ENABLE ROW LEVEL SECURITY')
    
#     # Create RLS policies
#     op.execute("""
#         CREATE POLICY tenant_isolation_wa_channel ON wa_channel
#             USING (tenant_id = current_setting('app.jwt_tenant')::uuid)
#     """)
#     op.execute("""
#         CREATE POLICY tenant_isolation_message ON message
#             USING (tenant_id = current_setting('app.jwt_tenant')::uuid)
#     """)
#     op.execute("""
#         CREATE POLICY tenant_isolation_outbox ON outbox
#             USING (tenant_id = current_setting('app.jwt_tenant')::uuid)
#     """)

# def downgrade():
#     op.drop_index('outbox_avail_idx', table_name='outbox')
#     op.drop_table('outbox')
#     op.drop_index('message_waid_idx', table_name='message')
#     op.drop_table('message')
#     op.drop_index('wa_channel_tenant_idx', table_name='wa_channel')
#     op.drop_table('wa_channel')