"""
Alembic Migration: Create Identity Schema
Revision ID: 001_identity_schema
Creates: identity schema with all 8 tables
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision = '001_identity_schema'
down_revision = None
branch_labels = ('identity',)
depends_on = None


def upgrade() -> None:
    """Create identity schema and tables"""
    
    # Create schema
    op.execute('CREATE SCHEMA IF NOT EXISTS identity')
    
    # 1. Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        schema='identity',
    )
    
    op.create_index('idx_orgs_slug', 'organizations', ['slug'], schema='identity')
    op.create_index('idx_orgs_industry', 'organizations', ['industry'], schema='identity', postgresql_where=sa.text('deleted_at IS NULL'))
    
    # 2. Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('password_hash', sa.Text, nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('email_verified', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('phone_verified', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('failed_login_attempts', sa.Integer, nullable=False, server_default='0'),
        sa.Column('locked_until', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),
        schema='identity',
    )
    
    op.create_index('idx_users_org', 'users', ['organization_id'], schema='identity')
    op.create_index('idx_users_email', 'users', ['email'], schema='identity', postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('idx_users_phone', 'users', ['phone'], schema='identity', postgresql_where=sa.text('deleted_at IS NULL'))
    
    # Enable RLS on users
    op.execute('ALTER TABLE identity.users ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY users_isolation ON identity.users
        USING (organization_id = current_setting('app.current_org_id')::UUID)
    """)
    
    # 3. Roles table
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('permissions', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('is_system', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        schema='identity',
    )
    
    op.create_index('idx_roles_org', 'roles', ['organization_id'], schema='identity')
    op.create_unique_constraint('uq_roles_org_name', 'roles', ['organization_id', 'name'], schema='identity')
    
    # 4. User-Role Mapping table
    op.create_table(
        'user_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.roles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('granted_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('granted_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.users.id'), nullable=True),
        schema='identity',
    )
    
    op.create_index('idx_user_roles_user', 'user_roles', ['user_id'], schema='identity')
    op.create_index('idx_user_roles_role', 'user_roles', ['role_id'], schema='identity')
    op.create_unique_constraint('uq_user_role', 'user_roles', ['user_id', 'role_id'], schema='identity')
    
    # 5. Refresh Tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.Text, unique=True, nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        schema='identity',
    )
    
    op.create_index('idx_refresh_tokens_user', 'refresh_tokens', ['user_id'], schema='identity')
    op.create_index('idx_refresh_tokens_expiry', 'refresh_tokens', ['expires_at'], schema='identity')
    
    # 6. Audit Logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.organizations.id'), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.users.id'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', postgresql.INET, nullable=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        schema='identity',
    )
    
    op.create_index('idx_audit_org_time', 'audit_logs', ['organization_id', sa.text('created_at DESC')], schema='identity')
    op.create_index('idx_audit_user_time', 'audit_logs', ['user_id', sa.text('created_at DESC')], schema='identity')
    op.create_index('idx_audit_action', 'audit_logs', ['action'], schema='identity')
    
    # 7. API Keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key_hash', sa.Text, unique=True, nullable=False),
        sa.Column('key_prefix', sa.String(20), nullable=False),
        sa.Column('permissions', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('last_used_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('revoked_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        schema='identity',
    )
    
    op.create_index('idx_api_keys_org', 'api_keys', ['organization_id'], schema='identity')
    op.create_index('idx_api_keys_prefix', 'api_keys', ['key_prefix'], schema='identity')
    
    # 8. Password Reset Tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.Text, unique=True, nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('used_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        schema='identity',
    )
    
    op.create_index('idx_reset_tokens_user', 'password_reset_tokens', ['user_id'], schema='identity')
    op.create_index('idx_reset_tokens_expiry', 'password_reset_tokens', ['expires_at'], schema='identity')

    # 9. Idempotency Keys table
    op.create_table(
        'idempotency_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('identity.organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('idempotency_key', sa.String(255), nullable=False),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('request_hash', sa.Text, nullable=False),
        sa.Column('response_code', sa.Integer, nullable=True),
        sa.Column('response_body', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        schema='identity',
    )
    op.create_index('idx_idempotency_org', 'idempotency_keys', ['organization_id'], schema='identity')
    op.create_index('idx_idempotency_expiry', 'idempotency_keys', ['expires_at'], schema='identity')
    op.create_unique_constraint(
        'uq_idempotency_key',
        'idempotency_keys',
        ['organization_id', 'endpoint', 'idempotency_key'],
        schema='identity',
    )


def downgrade() -> None:
    """Drop identity schema and all tables"""
    op.drop_table('idempotency_keys', schema='identity')
    op.drop_table('password_reset_tokens', schema='identity')
    op.drop_table('api_keys', schema='identity')
    op.drop_table('audit_logs', schema='identity')
    op.drop_table('refresh_tokens', schema='identity')
    op.drop_table('user_roles', schema='identity')
    op.drop_table('roles', schema='identity')
    op.drop_table('users', schema='identity')
    op.drop_table('organizations', schema='identity')
    
    op.execute('DROP SCHEMA IF EXISTS identity CASCADE')