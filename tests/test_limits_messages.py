import asyncio

import pytest

from fxocr.bot import messages as M
from fxocr.bot.limits import Busy, JobGate, RateLimiter


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_rate_limiter_window():
    c = Clock()
    rl = RateLimiter(2, 60, clock=c)
    assert rl.allow(1) and rl.allow(1)
    assert not rl.allow(1)
    assert rl.allow(2)  # other users unaffected
    c.t = 61
    assert rl.allow(1)


def test_rate_limiter_warns_once_per_window():
    c = Clock()
    rl = RateLimiter(1, 60, clock=c)
    assert rl.should_warn(1) and not rl.should_warn(1)
    c.t = 60
    assert rl.should_warn(1)


def test_job_gate_rejects_when_queue_full():
    async def run():
        gate = JobGate(concurrency=1, queue_max=1)
        release = asyncio.Event()

        async def hold():
            async with gate.slot():
                await release.wait()

        t1 = asyncio.create_task(hold())       # running
        await asyncio.sleep(0)
        t2 = asyncio.create_task(hold())       # waiting (queue = 1)
        await asyncio.sleep(0)
        with pytest.raises(Busy):
            async with gate.slot():
                pass
        release.set()
        await asyncio.gather(t1, t2)

    asyncio.run(run())


def test_ocr_output_is_html_escaped():
    out = M.result_html('<b>x</b> & <a href="tg://x">y</a></pre><script>')
    assert "<b>x" not in out and "<script>" not in out
    assert out.startswith("<pre>") and out.endswith("</pre>") and out.count("</pre>") == 1


def test_info_mentions_limits():
    s = M.info("tesseract", 10, 6, 60)
    assert "10 MB" in s and "6 images per 60 s" in s
