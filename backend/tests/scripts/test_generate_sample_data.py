import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_sample_data import generate


def test_generates_all_five_chats_parseable(tmp_path):
    out_dir = tmp_path / "sample"
    generate(storyline_path=REPO_ROOT / "scripts" / "sample_storyline.yaml", out_dir=out_dir)

    exports_dir = out_dir / "exports"
    gold_dir = out_dir / "gold"
    export_files = sorted(exports_dir.iterdir())
    assert len(export_files) == 5

    from app.ingestion.export_parser.detect import detect_format
    from app.ingestion.export_parser.zip_loader import load_export_bytes

    for f in export_files:
        text, _media = load_export_bytes(f.read_bytes(), filename=f.name)
        fmt = detect_format(text)
        assert fmt in ("android", "ios")

    gold_files = sorted(gold_dir.iterdir())
    assert len(gold_files) == 5
    all_types = set()
    for f in gold_files:
        items = json.loads(f.read_text())
        assert isinstance(items, list) and len(items) > 0
        for item in items:
            assert item["type"] in ("action", "decision", "risk", "issue")
            assert "title" in item and "evidence_text" in item
            all_types.add(item["type"])
    assert all_types == {"action", "decision", "risk", "issue"}


def test_generation_is_deterministic(tmp_path):
    out1, out2 = tmp_path / "a", tmp_path / "b"
    generate(storyline_path=REPO_ROOT / "scripts" / "sample_storyline.yaml", out_dir=out1)
    generate(storyline_path=REPO_ROOT / "scripts" / "sample_storyline.yaml", out_dir=out2)
    for f1 in sorted((out1 / "gold").iterdir()):
        f2 = out2 / "gold" / f1.name
        assert f1.read_text() == f2.read_text()
