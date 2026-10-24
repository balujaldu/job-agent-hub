from urllib.parse import quote


def content_disposition(filename: str, inline: bool) -> str:
    """A Content-Disposition header that survives non-ASCII names."""
    kind = "inline" if inline else "attachment"
    ascii_name = filename.encode("ascii", "ignore").decode() or "file"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
