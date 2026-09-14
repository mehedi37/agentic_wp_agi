from app.ingestion.export_parser.android import parse_android

TZ = "Asia/Dhaka"


def test_basic_two_messages():
    text = (
        "12/03/2026, 9:41 AM - Rafi: kal warehouse e jabo\n"
        "12/03/2026, 9:42 AM - Nadia: ok, notun update din"
    )
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert len(msgs) == 2
    assert msgs[0].sender == "Rafi" and msgs[0].text == "kal warehouse e jabo"
    assert msgs[1].sender == "Nadia" and not msgs[1].is_system


def test_multiline_message_appends_to_previous():
    text = (
        "12/03/2026, 9:41 AM - Rafi: line one\n"
        "line two continues\n"
        "line three continues\n"
        "12/03/2026, 9:42 AM - Nadia: separate message"
    )
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert len(msgs) == 2
    assert msgs[0].text == "line one\nline two continues\nline three continues"


def test_system_message_has_no_sender():
    text = "12/03/2026, 9:00 AM - Messages and calls are end-to-end encrypted."
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert msgs[0].sender is None and msgs[0].is_system is True


def test_media_omitted():
    text = "12/03/2026, 9:41 AM - Rafi: <Media omitted>"
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert msgs[0].media_type == "unknown" and msgs[0].text == ""


def test_invisible_marks_stripped():
    text = "‎12/03/2026, 9:41 AM - ‎Rafi: hello"
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert msgs[0].sender == "Rafi" and msgs[0].text == "hello"


def test_blank_lines_ignored():
    text = "12/03/2026, 9:41 AM - Rafi: hi\n\n\n12/03/2026, 9:42 AM - Nadia: hey"
    msgs = parse_android(text, date_order="DMY", tz=TZ)
    assert len(msgs) == 2
