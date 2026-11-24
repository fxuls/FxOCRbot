"""Run one OCR job in a fresh, resource-limited subprocess. The only API front-ends should call."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import resource
import signal
import sys
from dataclasses import dataclass

from fxocr.core.config import CoreConfig

log = logging.getLogger(__name__)

# Env passed to the worker: only what it needs. Notably NOT the bot token.
_PASS_ENV = ("PATH", "LANG", "LC_ALL", "TMPDIR", "HOME", "LITEPARSE_MODEL_DIR", "ORT_DYLIB_PATH",
             "TESSDATA_PREFIX")


@dataclass(frozen=True)
class OcrResult:
    ok: bool
    text: str = ""
    error: str = ""  # stable code: empty|too_large|unsupported_type|heif|too_many_pixels|corrupt|ocr_failed|timeout|internal
    ms: int = 0


def _limits(cfg: CoreConfig):
    def apply() -> None:
        mem = cfg.worker_mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        cpu = cfg.timeout_s + 5
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    return apply


def _worker_env(cfg: CoreConfig) -> dict[str, str]:
    env = {k: os.environ[k] for k in _PASS_ENV if k in os.environ}
    env.update({
        "FXOCR_ENGINE": cfg.engine,
        "FXOCR_MAX_FILE_MB": str(cfg.max_file_bytes // (1024 * 1024)),
        "FXOCR_MAX_PIXELS": str(cfg.max_pixels),
        "FXOCR_MAX_SIDE": str(cfg.max_side),
        "FXOCR_TIMEOUT_S": str(cfg.timeout_s),
        "OMP_NUM_THREADS": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return env


async def ocr_image_bytes(data: bytes, cfg: CoreConfig) -> OcrResult:
    if len(data) > cfg.max_file_bytes:
        return OcrResult(False, error="too_large")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-m", "fxocr.core.worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_worker_env(cfg),
        preexec_fn=_limits(cfg),
        start_new_session=True,
        close_fds=True,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(data), timeout=cfg.timeout_s + 10)
    except asyncio.TimeoutError:
        _kill(proc)
        await proc.wait()
        log.warning("ocr worker timed out")
        return OcrResult(False, error="timeout")
    except BaseException:
        _kill(proc)
        raise

    if err:
        log.warning("worker stderr: %s", err.decode(errors="replace")[-500:].strip())
    if proc.returncode != 0:
        log.warning("ocr worker exited rc=%s", proc.returncode)
        # SIGXCPU / SIGKILL / MemoryError → treat as an image we can't handle
        return OcrResult(False, error="timeout" if proc.returncode in (-signal.SIGXCPU, -signal.SIGKILL) else "corrupt")
    try:
        obj = json.loads(out.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        log.warning("ocr worker returned non-JSON output")
        return OcrResult(False, error="internal")
    if obj.get("ok"):
        return OcrResult(True, text=str(obj.get("text", "")), ms=int(obj.get("ms", 0)))
    return OcrResult(False, error=str(obj.get("error", "internal")))


def _kill(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
