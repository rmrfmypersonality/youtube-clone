import pytest

from app.services.video_files import sniff_container

MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
MOV = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  "
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic"


@pytest.mark.parametrize(
    "head,expected",
    [
        (MP4, "mp4"),
        (MOV, "mp4"),
        (WEBM, "matroska"),
        (PNG, None),
        (HEIC, None),
        (b"MZ" + b"\x00" * 30, None),
        (b"just some text, not a video", None),
        (b"\x00\x00\x00\x18ftyp", None),  # короче HEAD_SIZE
        (b"", None),
    ],
)
def test_sniff_container(head, expected):
    assert sniff_container(head) == expected