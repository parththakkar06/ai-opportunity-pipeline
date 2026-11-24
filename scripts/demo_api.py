#!/usr/bin/env python3
"""Demo mode: the real FastAPI app and pipeline, with fake LLM and search calls. Uses no API quota.

Useful for trying the UI, recording a walkthrough, or testing the live progress view.

    python scripts/demo_api.py                 # serves on http://127.0.0.1:8010
    cd frontend && API_PROXY_TARGET=http://127.0.0.1:8010 npm run dev -- --port 5174

Behaviour:
- Each model call takes DEMO_DELAY seconds (default 2.5) so progress is visible.
- Stage 3 shows a model fallback note ("… unavailable …; switching to …").
- A company name containing "fail" stops at stage 3 the first time, so you can try Resume.
- Reports are written to a temporary demo folder, never to outputs/.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("OUTPUTS_DIR", str(Path(tempfile.gettempdir()) / "ai-opportunity-demo-outputs"))
os.environ.setdefault("PRICE_INPUT_PER_MTOK", "0")
os.environ.setdefault("PRICE_OUTPUT_PER_MTOK", "0")

import api.index as api  # noqa: E402
from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import FakeLLM, FakeProvider, FakeResearch  # noqa: E402
from utils.config import Settings  # noqa: E402
from utils.llm import LLMError  # noqa: E402

DELAY = float(os.getenv("DEMO_DELAY", "2.5"))
_failed_once: set[str] = set()


class DemoLLM(FakeLLM):
    def __init__(self, company: str):
        super().__init__()
        self.company = company

    def _structured_once(self, **kw):
        time.sleep(DELAY)
        name = kw["schema"].__name__
        if name == "AIOpportunities":
            self.notify("baidu/ernie-5.5-flash-preview:free unavailable (rate-limited: Baidu: temporarily "
                        "rate-limited upstream); switching to google/gemma-4-31b-it:free")
            if "fail" in self.company.lower() and self.company not in _failed_once:
                _failed_once.add(self.company)
                raise LLMError("Every OpenRouter model is busy or unavailable right now (demo failure). "
                               "Wait a few minutes and use Resume.")
        result = super()._structured_once(**kw)
        if name == "BusinessProfileDraft":
            result.business_name = self.company
        return result

    def _text_once(self, **kw):
        time.sleep(DELAY * 2)
        return super()._text_once(**kw)


class DemoResearch(FakeResearch):
    def search_many(self, queries, cache=None):
        time.sleep(DELAY)
        return super().search_many(queries, cache=cache)


def demo_runner(company, *, url=None, context=None, ui=None, build_prototype=None, from_step=1, slug=None):
    settings = Settings(outputs_dir=Path(os.environ["OUTPUTS_DIR"]), model="demo/fake-model:free",
                        builder_model="demo/fake-model:free", cheap_model="demo/fake-model:free",
                        provider="demo")
    research = DemoResearch([FakeProvider("tavily", results=6)])
    return run_pipeline(company, url=url or f"{re.sub(r'[^a-z0-9]+', '', company.lower())}.example",
                        context=context, settings=settings, llm=DemoLLM(company), research=research, ui=ui,
                        build_prototype=build_prototype, from_step=from_step, slug=slug)


api.RUNNER = demo_runner

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("DEMO_PORT", "8010"))
    print(f"Demo API (no quota used) on http://127.0.0.1:{port} · reports in {os.environ['OUTPUTS_DIR']}")
    uvicorn.run(api.app, host="127.0.0.1", port=port)
