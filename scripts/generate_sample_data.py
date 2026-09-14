"""Deterministic sample-data generator (PLAN.md §11 / T1.2).

Reads `scripts/sample_storyline.yaml` and renders each chat to its
configured export format (Android .txt or iOS .zip containing `_chat.txt`),
plus a gold-labels JSON file per chat. No LLM call -- fully deterministic,
so re-running produces byte-identical output.
"""
import io
import json
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ANCHOR_DATE = date(2026, 1, 5)
TZ = ZoneInfo("Asia/Dhaka")


def _render_android_line(ts: datetime, sender: str | None, text: str) -> str:
    time_str = ts.strftime("%I:%M %p").lstrip("0")
    date_str = ts.strftime("%d/%m/%Y")
    prefix = f"{date_str}, {time_str} - "
    return prefix + (f"{sender}: {text}" if sender else text)


def _render_ios_line(ts: datetime, sender: str | None, text: str) -> str:
    time_str = ts.strftime("%I:%M:%S %p").lstrip("0")
    date_str = ts.strftime("%d/%m/%Y")
    prefix = f"[{date_str}, {time_str}] "
    return prefix + (f"{sender}: {text}" if sender else text)


def _render_chat(chat: dict) -> tuple[str, list[dict]]:
    lines: list[str] = []
    gold_items: list[dict] = []
    render = _render_android_line if chat["export_format"] == "android" else _render_ios_line

    for msg in chat["messages"]:
        ts = datetime.combine(
            ANCHOR_DATE + timedelta(days=msg["day"]),
            datetime.strptime(msg["time"], "%H:%M").time(),
            tzinfo=TZ,
        )
        sender = None if msg.get("system") else msg["sender"]
        lines.append(render(ts, sender, msg["text"]))
        if "gold" in msg:
            gold = dict(msg["gold"])
            gold["evidence_text"] = msg["text"]
            gold["chat_key"] = chat["key"]
            gold_items.append(gold)

    return "\n".join(lines), gold_items


def generate(*, storyline_path: Path, out_dir: Path) -> None:
    storyline = yaml.safe_load(storyline_path.read_text(encoding="utf-8"))
    exports_dir = out_dir / "exports"
    gold_dir = out_dir / "gold"
    exports_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    for chat in storyline["chats"]:
        text, gold_items = _render_chat(chat)
        if chat["export_format"] == "android":
            (exports_dir / f"{chat['key']}.txt").write_text(text, encoding="utf-8")
        else:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("_chat.txt", text.encode("utf-8"))
            (exports_dir / f"{chat['key']}.zip").write_bytes(buf.getvalue())

        (gold_dir / f"{chat['key']}.json").write_text(
            json.dumps(gold_items, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    generate(
        storyline_path=repo_root / "scripts" / "sample_storyline.yaml",
        out_dir=repo_root / "data" / "sample",
    )
