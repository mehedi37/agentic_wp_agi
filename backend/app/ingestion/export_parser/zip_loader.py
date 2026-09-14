import io
import zipfile


class NoChatFileError(ValueError):
    pass


def load_export_bytes(file_bytes: bytes, *, filename: str) -> tuple[str, list[str]]:
    """Returns (chat_text, media_filenames). `media_filenames` lists names
    only -- media content is never stored (PLAN.md §10: media is metadata
    only)."""
    if filename.lower().endswith(".zip") or file_bytes[:2] == b"PK":
        try:
            zf = zipfile.ZipFile(io.BytesIO(file_bytes))
        except zipfile.BadZipFile as exc:
            raise NoChatFileError(f"{filename} is not a valid zip file") from exc
        with zf:
            chat_name = next(
                (n for n in zf.namelist() if n.lower().endswith("_chat.txt") or n.lower() == "_chat.txt"),
                None,
            )
            if chat_name is None:
                raise NoChatFileError(f"no _chat.txt found in {filename}")
            chat_text = zf.read(chat_name).decode("utf-8", errors="replace")
            media_names = sorted(n for n in zf.namelist() if n != chat_name and not n.endswith("/"))
            return chat_text, media_names
    return file_bytes.decode("utf-8", errors="replace"), []
