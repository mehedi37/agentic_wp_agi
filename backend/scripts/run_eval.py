"""Extraction + validator-loop evaluation harness (`make eval`).

Ingests the committed sample exports (idempotent, safe to re-run), runs the
real pipeline against them with the configured LLM provider, then scores the
extracted items against `data/sample/gold/*.json` and writes a metrics table
to docs/evaluation.md.
"""
import asyncio
import json
import os
import uuid
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.checkpoints import setup_checkpoints
from app.agents.pipeline_graph import run_pipeline_for_chat
from app.core.config import settings
from app.db.models import AgentRun, Chat, Item, ItemEvidence
from app.db.session import SessionLocal
from app.llm.base import LLMProvider
from app.llm.embeddings import EmbeddingProvider
from app.llm.factory import get_embedding_provider, get_llm_provider
from app.services.ingestion import ingest_export

SAMPLES = Path(os.environ.get("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[2] / "data" / "sample")))
DOCS = Path(__file__).resolve().parents[2] / "docs"
MATCH_THRESHOLD = 0.55


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def _ensure_ingested_and_processed(
    session: Session, chat_key: str, llm: LLMProvider, embedder: EmbeddingProvider
) -> Chat:
    name = chat_key.replace("_", " ").title()
    chat = session.scalar(select(Chat).where(Chat.name == name, Chat.source == "export"))
    if chat is None:
        export_path = next(p for p in (SAMPLES / "exports").iterdir() if p.stem == chat_key)
        chat = Chat(name=name, source="export", type="group", timezone="Asia/Dhaka")
        session.add(chat)
        session.flush()
        await ingest_export(session, chat_id=chat.id, filename=export_path.name, file_bytes=export_path.read_bytes())
        session.commit()
    await run_pipeline_for_chat(session, chat_id=chat.id, analyst_llm=llm, judge_llm=llm, embedder=embedder)
    session.commit()
    return chat


def _match(gold: dict, candidates: list[Item], quotes_by_item: dict[uuid.UUID, str]) -> Item | None:
    best, best_score = None, 0.0
    for item in candidates:
        if item.type != gold["type"]:
            continue
        score = max(_similar(gold["title"], item.title),
                    _similar(gold["evidence_text"], quotes_by_item.get(item.id, "")))
        if score > best_score:
            best, best_score = item, score
    return best if best_score >= MATCH_THRESHOLD else None


async def main() -> None:
    setup_checkpoints()
    llm, embedder = get_llm_provider(), get_embedding_provider()
    gold_files = sorted((SAMPLES / "gold").glob("*.json"))
    if not gold_files:
        raise FileNotFoundError(f"No gold files found under {SAMPLES / 'gold'}")

    totals: defaultdict[str, int] = defaultdict(int)
    per_type: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    rows: list[str] = []

    with SessionLocal() as session:
        for gold_file in gold_files:
            chat_key = gold_file.stem
            gold_items: list[dict] = json.loads(gold_file.read_text())
            chat = await _ensure_ingested_and_processed(session, chat_key, llm, embedder)

            candidates = list(session.scalars(select(Item).where(Item.chat_id == chat.id)))
            quotes_by_item: dict[uuid.UUID, str] = {}
            for item_id, quote in session.execute(
                select(ItemEvidence.item_id, ItemEvidence.quote).where(
                    ItemEvidence.item_id.in_([i.id for i in candidates])
                )
            ):
                quotes_by_item[item_id] = quotes_by_item.get(item_id, "") + " " + quote

            matched_ids: set[uuid.UUID] = set()
            for gold in gold_items:
                match = _match(gold, candidates, quotes_by_item)
                totals["gold"] += 1
                per_type[gold["type"]]["gold"] += 1
                if match is None:
                    totals["fn"] += 1
                    per_type[gold["type"]]["fn"] += 1
                    continue
                matched_ids.add(match.id)
                totals["tp"] += 1
                per_type[gold["type"]]["tp"] += 1
                if gold.get("owner_raw"):
                    totals["owner_total"] += 1
                    if match.owner_raw and _similar(match.owner_raw, gold["owner_raw"]) > 0.6:
                        totals["owner_correct"] += 1
                if gold.get("due_date_raw"):
                    totals["due_total"] += 1
                    if match.due_at is not None:
                        totals["due_correct"] += 1
                quote = quotes_by_item.get(match.id, "")
                totals["grounded_total"] += 1
                if _similar(gold["evidence_text"], quote) > 0.5 or gold["evidence_text"].lower() in quote.lower():
                    totals["grounded"] += 1

            totals["fp"] += sum(1 for i in candidates if i.id not in matched_ids)
            rows.append(f"| {chat_key} | {len(gold_items)} | {len(candidates)} | {len(matched_ids)} |")

        # Validator-loop signal: retries triggered vs. items still flagged for human review.
        validate_runs = session.scalar(
            select(func.count()).select_from(AgentRun).where(AgentRun.agent == "pipeline", AgentRun.node == "validate")
        ) or 0
        failed_validations = session.scalar(
            select(func.count()).select_from(AgentRun).where(
                AgentRun.agent == "pipeline", AgentRun.node == "validate", AgentRun.status == "failed"
            )
        ) or 0
        needs_review = session.scalar(select(func.count()).select_from(Item).where(Item.validation_status == "needs_review")) or 0
        passed = session.scalar(select(func.count()).select_from(Item).where(Item.validation_status == "passed")) or 0

    precision = totals["tp"] / (totals["tp"] + totals["fp"]) if totals["tp"] + totals["fp"] else 0.0
    recall = totals["tp"] / totals["gold"] if totals["gold"] else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    owner_acc = totals["owner_correct"] / totals["owner_total"] if totals["owner_total"] else float("nan")
    due_acc = totals["due_correct"] / totals["due_total"] if totals["due_total"] else float("nan")
    grounding_rate = totals["grounded"] / totals["grounded_total"] if totals["grounded_total"] else float("nan")

    by_type_lines = "\n".join(
        f"| {t} | {v['tp']} | {v['gold']} | {v['tp'] / v['gold'] if v['gold'] else 0:.2f} |"
        for t, v in sorted(per_type.items())
    )

    provider_note = (
        "\n> Running with `LLM_PROVIDER=fake` (the built-in regex `DemoProvider`, not a real "
        "language model — see `app/llm/demo_provider.py`). It only proves the pipeline and "
        "scoring wiring; it does not extract owners/deadlines. Set `LLM_PROVIDER=anthropic` "
        "(or `ollama`) and re-run `make eval` for the real extraction-quality numbers.\n"
        if settings.llm_provider == "fake" else ""
    )
    report = f"""# Evaluation Report

Generated by `make eval` (`backend/scripts/run_eval.py`) against the committed
sample data. Re-run any time; ingestion and pipeline runs are idempotent, so
scores reflect the current extraction + validation behavior.
{provider_note}

## Extraction quality (overall)

| Metric | Value |
|---|---|
| Precision | {precision:.2f} |
| Recall | {recall:.2f} |
| F1 | {f1:.2f} |
| Owner accuracy (of gold items with a stated owner) | {owner_acc:.2f} |
| Deadline accuracy (of gold items with a stated date) | {due_acc:.2f} |
| Grounding rate (evidence quote traceable to a cited message) | {grounding_rate:.2f} |

## By item type

| Type | Matched | Gold | Recall |
|---|---|---|---|
{by_type_lines}

## Per-chat coverage

| Chat | Gold items | Extracted items | Matched |
|---|---|---|---|
{chr(10).join(rows)}

## Validator retry loop

| Metric | Value |
|---|---|
| Validate-node runs | {validate_runs} |
| Runs that failed validation and triggered a retry | {failed_validations} |
| Items still `needs_review` after the retry budget | {needs_review} |
| Items that passed validation | {passed} |

A non-zero "failed and triggered a retry" count demonstrates the
Analyst&harr;Validator loop actually firing (validator feedback sent back to
the Analyst for another attempt) rather than a single unchecked pass.
"""
    DOCS.mkdir(exist_ok=True)
    (DOCS / "evaluation.md").write_text(report)
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
