import asyncio
import contextlib
import json
import math
from asyncio.subprocess import DEVNULL, PIPE
from dataclasses import dataclass
from pathlib import Path


class ProcessingError(Exception):
    """Сбой, который имеет смысл повторить (таймаут, нехватка ресурсов, падение ffmpeg)."""


class CommandFailed(ProcessingError):
    pass


class PermanentError(Exception):
    """Повторять бессмысленно: файл не является корректным видео."""


@dataclass
class ProbeResult:
    duration: float
    width: int
    height: int


# -protocol_whitelist file: ffmpeg читает только локальные файлы, никакой сети и вложенных плейлистов
_INPUT_OPTS = ["-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-protocol_whitelist", "file"]


def _kill(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):
        proc.kill()


async def _run(args: list[str], timeout: float) -> bytes:
    # Без shell: аргументы передаются списком
    proc = await asyncio.create_subprocess_exec(*args, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        _kill(proc)
        await proc.wait()
        raise ProcessingError(f"{args[0]}: таймаут {timeout:.0f} с") from None
    except BaseException:  # в том числе отмена задачи при остановке воркера
        _kill(proc)
        await proc.wait()
        raise
    if proc.returncode != 0:
        raise CommandFailed(f"{args[0]}: {stderr.decode(errors='replace')[-1500:]}")
    return stdout


async def probe(path: Path, timeout: float) -> ProbeResult:
    try:
        out = await _run(
            [
                "ffprobe", "-v", "error", "-protocol_whitelist", "file",
                "-print_format", "json", "-show_format", "-show_streams", str(path),
            ],
            timeout,
        )
    except CommandFailed as e:
        raise PermanentError("Файл не удалось прочитать как видео") from e

    data = json.loads(out)
    video = next(
        (
            s
            for s in data.get("streams", [])
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    if video is None:
        raise PermanentError("В файле нет видеодорожки")

    raw_duration = data.get("format", {}).get("duration") or video.get("duration")
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        raise PermanentError("Не удалось определить длительность") from None
    if not math.isfinite(duration) or duration <= 0:
        raise PermanentError("Некорректная длительность видео")

    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    if width <= 0 or height <= 0:
        raise PermanentError("Не удалось определить разрешение")
    return ProbeResult(duration=duration, width=width, height=height)


async def _ensure_output(dst: Path) -> None:
    if not dst.exists() or dst.stat().st_size == 0:
        raise ProcessingError(f"ffmpeg не создал файл {dst.name}")


async def transcode(src: Path, dst: Path, height: int, timeout: float) -> None:
    """H.264 + AAC, faststart, высота не больше `height` (без апскейла)."""
    await _run(
        [
            "ffmpeg", *_INPUT_OPTS, "-i", str(src),
            "-map", "0:v:0", "-map", "0:a:0?", "-map_metadata", "-1",
            "-vf", f"scale=-2:'min({height},ih)'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ac", "2",
            "-movflags", "+faststart",
            str(dst),
        ],
        timeout,
    )
    await _ensure_output(dst)


async def thumbnail(src: Path, dst: Path, at: float, timeout: float) -> None:
    await _run(
        [
            "ffmpeg", *_INPUT_OPTS, "-ss", f"{at:.3f}", "-i", str(src),
            "-map", "0:v:0", "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4",
            str(dst),
        ],
        timeout,
    )
    await _ensure_output(dst)