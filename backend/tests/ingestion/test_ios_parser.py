from app.ingestion.export_parser.ios import parse_ios

TZ = "Asia/Dhaka"


def test_basic_two_messages():
    text = (
        "[12/03/2026, 09:41:03] Rafi: kal warehouse e jabo\n"
        "[12/03/2026, 09:42:11] Nadia: ok, notun update din"
    )
    msgs = parse_ios(text, date_order="DMY", tz=TZ)
    assert len(msgs) == 2
    assert msgs[0].sender == "Rafi"


def test_multiline_message_appends_to_previous():
    text = (
        "[12/03/2026, 09:41:03] Rafi: line one\n"
        "line two continues\n"
        "[12/03/2026, 09:42:11] Nadia: separate"
    )
    msgs = parse_ios(text, date_order="DMY", tz=TZ)
    assert msgs[0].text == "line one\nline two continues"


def test_system_message_has_no_sender():
    text = "[12/03/2026, 09:00:00] Messages and calls are end-to-end encrypted."
    msgs = parse_ios(text, date_order="DMY", tz=TZ)
    assert msgs[0].sender is None and msgs[0].is_system is True


def test_media_omitted_variants():
    text = (
        "[12/03/2026, 09:41:03] Rafi: image omitted\n"
        "[12/03/2026, 09:42:00] Nadia: video omitted\n"
        "[12/03/2026, 09:43:00] Rafi: ‎document omitted"
    )
    msgs = parse_ios(text, date_order="DMY", tz=TZ)
    assert [m.media_type for m in msgs] == ["image", "video", "document"]


def test_12h_am_pm_variant():
    text = "[3/12/26, 9:41:03 AM] Rafi: hi"
    msgs = parse_ios(text, date_order="MDY", tz=TZ)
    assert msgs[0].ts.hour == 9
