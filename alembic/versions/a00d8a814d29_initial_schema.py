"""initial_schema

Revision ID: a00d8a814d29
Revises: 
Create Date: 2026-11-01 16:42:02.063359

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a00d8a814d29'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Contacts Table
    op.create_table(
        'contacts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('consent_status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('consent_date', sa.DateTime(), nullable=True),
        sa.Column('consent_source', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_contacts_phone', 'contacts', ['phone'], unique=True)

    # 2. Templates Table
    op.create_table(
        'templates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('language', sa.String(length=20), server_default='en_US', nullable=False),
        sa.Column('body_preview', sa.Text(), nullable=True),
        sa.Column('variables', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_templates_name', 'templates', ['name'], unique=True)

    # 3. Campaigns Table
    op.create_table(
        'campaigns',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('templates.id'), nullable=False),
        sa.Column('audience_filter', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_campaigns_template_id', 'campaigns', ['template_id'], unique=False)

    # 4. Messages Log Table
    op.create_table(
        'messages_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('campaign_id', sa.Integer(), sa.ForeignKey('campaigns.id'), nullable=True),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('contacts.id'), nullable=False),
        sa.Column('whatsapp_message_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='sent', nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_messages_log_campaign_id', 'messages_log', ['campaign_id'], unique=False)
    op.create_index('ix_messages_log_contact_id', 'messages_log', ['contact_id'], unique=False)
    op.create_index('ix_messages_log_whatsapp_message_id', 'messages_log', ['whatsapp_message_id'], unique=False)


def downgrade() -> None:
    op.drop_table('messages_log')
    op.drop_table('campaigns')
    op.drop_table('templates')
    op.drop_table('contacts')
