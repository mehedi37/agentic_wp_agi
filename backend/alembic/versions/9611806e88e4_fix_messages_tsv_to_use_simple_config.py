"""fix messages.tsv to use the `simple` text-search config

PLAN.md §7 requires `simple`, not `english`, specifically so Bangla and
Banglish tokens are not mangled by English stemming/stopwords. The Phase 0
migration (0002) used `english` by mistake; this corrects it without
touching that already-reviewed migration file.

Revision ID: 9611806e88e4
Revises: 052e11d94eee
Create Date: 2026-09-14 19:41:30.637591

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9611806e88e4'
down_revision: Union[str, Sequence[str], None] = '052e11d94eee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_messages_tsv_gin")
    op.execute("ALTER TABLE messages DROP COLUMN tsv")
    op.execute(
        "ALTER TABLE messages "
        "ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED"
    )
    op.execute("CREATE INDEX ix_messages_tsv_gin ON messages USING gin (tsv)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_messages_tsv_gin")
    op.execute("ALTER TABLE messages DROP COLUMN tsv")
    op.execute(
        "ALTER TABLE messages "
        "ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
    )
    op.execute("CREATE INDEX ix_messages_tsv_gin ON messages USING gin (tsv)")
