"""search indexes and segment message id types

Restores three Phase-0 deliverables (PLAN.md T0.2/T0.3, §8 Data Model)
that were missing from 0001_initial_schema.py:

1. `messages.tsv` -- a `tsvector` generated column (STORED, English config)
   over `messages.text`, plus a GIN index, so full-text search (R5 hybrid
   search) works without an application-level population job.
2. HNSW vector indexes (cosine distance, matching PLAN.md's "pgvector
   cosine top-k" retrieval) on every `VECTOR` embedding column that had no
   index yet: `messages.embedding`, `segments.embedding`, `items.embedding`,
   `entities.embedding`, `summaries.embedding`.
3. `segments.message_ids` changed from `text[]` to `uuid[]` to match
   `messages.id`'s real type (Segment.message_ids stored UUIDs as strings).

Revision ID: d3539cb1e81a
Revises: 4ed9dbc53b55
Create Date: 2026-09-14 14:46:10.835206

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3539cb1e81a'
down_revision: Union[str, Sequence[str], None] = '4ed9dbc53b55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Full-text search column + index over message content.
    op.execute(
        "ALTER TABLE messages "
        "ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
    )
    op.execute("CREATE INDEX ix_messages_tsv_gin ON messages USING gin (tsv)")

    # 2. Vector similarity indexes (HNSW, cosine distance) on every
    # embedding column that did not yet have one.
    op.execute(
        "CREATE INDEX ix_messages_embedding_hnsw ON messages "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_segments_embedding_hnsw ON segments "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_items_embedding_hnsw ON items "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_entities_embedding_hnsw ON entities "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_summaries_embedding_hnsw ON summaries "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # 3. segments.message_ids: text[] holding UUID strings -> real uuid[].
    op.execute(
        "ALTER TABLE segments ALTER COLUMN message_ids TYPE uuid[] "
        "USING message_ids::uuid[]"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "ALTER TABLE segments ALTER COLUMN message_ids TYPE text[] "
        "USING message_ids::text[]"
    )

    op.execute("DROP INDEX IF EXISTS ix_summaries_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_entities_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_items_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_segments_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_messages_embedding_hnsw")

    op.execute("DROP INDEX IF EXISTS ix_messages_tsv_gin")
    op.execute("ALTER TABLE messages DROP COLUMN tsv")
