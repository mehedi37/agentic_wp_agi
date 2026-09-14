from app.ingestion.export_parser.detect import detect_format


def test_detects_android():
    text = "12/03/2026, 9:41 AM - Rafi: kal delivery hobe\n12/03/2026, 9:42 AM - Nadia: ok"
    assert detect_format(text) == "android"


def test_detects_ios():
    text = "[12/03/2026, 09:41:03] Rafi: kal delivery hobe\n[12/03/2026, 09:42:11] Nadia: ok"
    assert detect_format(text) == "ios"


def test_detects_android_with_invisible_marks():
    text = "‎12/03/2026, 9:41 AM - Rafi: hi"
    assert detect_format(text) == "android"


def test_unrecognized_raises():
    import pytest

    from app.ingestion.export_parser.detect import UnrecognizedFormatError
    with pytest.raises(UnrecognizedFormatError):
        detect_format("this is not a whatsapp export at all")
