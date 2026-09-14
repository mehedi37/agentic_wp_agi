"""chat state table

Revision ID: 052e11d94eee
Revises: d3539cb1e81a
Create Date: 2026-09-14 19:41:17.464707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '052e11d94eee'
down_revision: Union[str, Sequence[str], None] = 'd3539cb1e81a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'chat_state',
        sa.Column('chat_id', sa.UUID(), nullable=False),
        sa.Column('rolling_summary', sa.Text(), nullable=True),
        sa.Column('last_message_ts', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('chat_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('chat_state')
