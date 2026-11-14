HEAD_SIZE = 12

# Контейнеры ftyp, которые на самом деле картинки (HEIC/AVIF)
_IMAGE_BRANDS = {
    b"heic", b"heix", b"heim", b"heis", b"hevm", b"hevs",
    b"mif1", b"msf1", b"avif", b"avis",
}


def sniff_container(head: bytes) -> str | None:
    """Определяет контейнер по magic bytes. None, если это не поддерживаемое видео."""
    if len(head) < HEAD_SIZE:
        return None
    if head[:4] == b"\x1a\x45\xdf\xa3":  # EBML: WebM и MKV
        return "matroska"
    if head[4:8] == b"ftyp" and head[8:12] not in _IMAGE_BRANDS:  # MP4, MOV, M4V
        return "mp4"
    return None