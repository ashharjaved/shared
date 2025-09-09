"""Add plans and subscriptions

Revision ID: 002_add_plans_and_subscriptions
Revises: 001_initial_identity_tables
Create Date: 2025-09-06 05:24:17.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_plans_and_subscriptions'
down_revision = '001_initial_identity_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE plan_slug AS ENUM ('free', 'basic', 'professional', 'enterprise')")
    op.execute("CREATE TYPE subscription_status AS ENUM ('active', 'pending', 'canceled', 'expired')")
    
    # Create plans table
    op.create_table(
        'plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('slug', sa.Enum('free', 'starter', 'professional', 'enterprise', name='plan_slug'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('price_inr', sa.Float(), nullable=False),
        sa.Column('features', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_plans_slug', 'plans', ['slug'], unique=True)
    
    # Create tenant_plan_subscriptions table
    op.create_table(
        'tenant_plan_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('active', 'pending', 'canceled', 'expired', name='subscription_status'), nullable=False),
        sa.Column('start_at', sa.DateTime(), nullable=False),
        sa.Column('end_at', sa.DateTime(), nullable=False),
        sa.Column('meta', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_subscriptions_tenant_plan', 'tenant_plan_subscriptions', ['tenant_id', 'plan_id'], unique=True)
    
    # Enable RLS
    op.execute('ALTER TABLE plans ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE tenant_plan_subscriptions ENABLE ROW LEVEL SECURITY')
    
    # Create RLS policies
    op.execute("""
        CREATE POLICY plans_read_all ON plans
            USING (true)  -- Plans are readable by all authenticated users
    """)
    
    op.execute("""
        CREATE POLICY subscriptions_isolation ON tenant_plan_subscriptions
            USING (tenant_id = current_setting('app.jwt_tenant')::uuid)
    """)
    
    # Add updated_at trigger for plans and subscriptions
    for table in ['plans', 'tenant_plan_subscriptions']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    # Drop triggers
    for table in ['plans', 'tenant_plan_subscriptions']:
        op.execute(f'DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table}')
    
    # Drop tables
    op.drop_table('tenant_plan_subscriptions')
    op.drop_table('plans')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS subscription_status')
    op.execute('DROP TYPE IF EXISTS plan_slug')