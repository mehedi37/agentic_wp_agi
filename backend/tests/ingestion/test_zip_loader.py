import io
import zipfile

from app.ingestion.export_parser.zip_loader import load_export_bytes


def _make_zip(chat_txt: bytes, extra_files: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("_chat.txt", chat_txt)
        for name, content in (extra_files or {}).items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_plain_txt_bytes_returned_as_is():
    text, media_names = load_export_bytes(b"12/03/2026, 9:41 AM - Rafi: hi", filename="chat.txt")
    assert text == "12/03/2026, 9:41 AM - Rafi: hi"
    assert media_names == []


def test_zip_extracts_chat_txt_and_lists_media():
    zip_bytes = _make_zip(
        b"12/03/2026, 9:41 AM - Rafi: hi\n12/03/2026, 9:42 AM - Rafi: <Media omitted>",
        extra_files={"IMG-20260312-WA0001.jpg": b"\xff\xd8\xff"},
    )
    text, media_names = load_export_bytes(zip_bytes, filename="chat_export.zip")
    assert "Rafi: hi" in text
    assert media_names == ["IMG-20260312-WA0001.jpg"]


def test_zip_without_chat_txt_raises():
    import pytest

    from app.ingestion.export_parser.zip_loader import NoChatFileError

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", b"not a chat export")
    with pytest.raises(NoChatFileError):
        load_export_bytes(buf.getvalue(), filename="bad.zip")
