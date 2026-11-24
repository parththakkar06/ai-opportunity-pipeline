"""FastAPI backend for the AI Opportunity Pipeline.

Run from the project root:

    uvicorn api.index:app --reload --port 8000

Endpoints
    GET  /api/health                     provider / key status (no API call)
    GET  /api/examples                   saved runs in outputs/
    GET  /api/examples/{slug}            one saved run as the 5-section report + markdown
    GET  /api/examples/{slug}/prototype  the run's interactive HTML prototype, if built
    POST /api/analyze/stream             run the pipeline; Server-Sent Events with live stage progress
    POST /api/analyze                    run the pipeline; one JSON response at the end
"""
from __future__ import annotations

import io
import json
import os
import queue
import re
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field, field_validator  # noqa: E402
from rich.console import Console  # noqa: E402

from agents.base import PROFILE_JSON, PROTOTYPE_HTML, STAGE_TITLES, find_file  # noqa: E402
from agents.report import build_report, render_ceo_pitch_text, render_report_markdown  # noqa: E402
from run_pipeline import PipelineError, run_pipeline  # noqa: E402
from utils.config import DEFAULT_OUTPUTS_DIR, ConfigError, load_settings  # noqa: E402
from utils.console import PipelineUI  # noqa: E402
from utils.costs import AgentTotals, fmt_cost  # noqa: E402
from utils.io import HandoffError, slugify  # noqa: E402
from utils.llm import LLMError  # noqa: E402

app = FastAPI(title="AI Opportunity Pipeline API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Swappable in tests: same signature as run_pipeline.run_pipeline.
RUNNER: Callable[..., Any] = run_pipeline

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,120}$")
_active_runs: set[str] = set()
_active_lock = threading.Lock()


def outputs_root() -> Path:
    raw = os.getenv("OUTPUTS_DIR")
    path = Path(raw).expanduser() if raw else DEFAULT_OUTPUTS_DIR
    return path if path.is_absolute() else (ROOT / path)


def run_dir(slug: str) -> Path:
    if not SLUG_RE.match(slug):
        raise HTTPException(400, "Invalid run id.")
    path = (outputs_root() / slug).resolve()
    if path.parent != outputs_root().resolve() or not path.is_dir():
        raise HTTPException(404, f"No saved run named {slug!r}.")
    return path


def report_payload(out_dir: Path) -> dict[str, Any]:
    report = build_report(out_dir)
    return {
        "report": report.model_dump(mode="json"),
        "markdown": render_report_markdown(report),
        "pitch_text": render_ceo_pitch_text(report),
        "prototype_url": f"/api/examples/{out_dir.name}/prototype" if report.prototype_available else None,
    }


# --------------------------------------------------------------------------- read-only endpoints
@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        s = load_settings()
    except ConfigError as exc:
        return {"status": "config_error", "message": str(exc)}
    key_var = {"gemini": "GEMINI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}.get(s.provider, "OPENAI_API_KEY")
    has_key = bool(os.getenv(key_var) or (s.provider == "gemini" and os.getenv("GOOGLE_API_KEY")))
    search = "tavily" if s.tavily_api_key else "serper" if s.serper_api_key else "duckduckgo"
    return {"status": "ok", "provider": s.provider, "model": s.model, "llm_key_configured": has_key,
            "search_provider": search, "stages": STAGE_TITLES}


def _input_name(run: Path) -> Optional[str]:
    """The company name originally typed for this run (from 00_run_meta.json), if recorded."""
    meta = run / "00_run_meta.json"
    try:
        return json.loads(meta.read_text()).get("business_name") if meta.exists() else None
    except (ValueError, OSError):
        return None


@app.get("/api/examples")
def list_examples() -> list[dict[str, Any]]:
    root = outputs_root()
    runs = []
    if not root.is_dir():
        return runs
    for d in root.iterdir():
        if not d.is_dir() or not SLUG_RE.match(d.name) or find_file(d, PROFILE_JSON) is None:
            continue
        try:
            r = build_report(d)
        except HandoffError:
            continue
        runs.append({
            "slug": d.name, "business_name": r.business_name, "generated_at": r.generated_at,
            "stages_completed": r.stages_completed, "complete": r.stages_completed == [1, 2, 3, 4],
            "next_stage": next((s for s in (1, 2, 3, 4) if s not in r.stages_completed), None),
            "data_quality": r.data_quality, "prototype_available": r.prototype_available,
            "website": r.company_overview.website, "industry": r.company_overview.industry,
            "input_name": _input_name(d) or r.business_name,
        })
    runs.sort(key=lambda x: x["generated_at"] or "", reverse=True)
    return runs


@app.get("/api/examples/{slug}")
def get_example(slug: str) -> dict[str, Any]:
    try:
        return report_payload(run_dir(slug))
    except HandoffError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/examples/{slug}/prototype")
def get_prototype(slug: str) -> FileResponse:
    path = run_dir(slug) / PROTOTYPE_HTML
    if not path.exists():
        raise HTTPException(404, "No prototype was built for this run.")
    return FileResponse(path, media_type="text/html")


# --------------------------------------------------------------------------- running the pipeline
class AnalyzeRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    url: Optional[str] = Field(None, max_length=200)
    context: Optional[str] = Field(None, max_length=300)
    include_prototype: bool = True
    from_stage: int = Field(1, ge=1, le=4, description="Resume from this stage, reusing saved earlier stages")
    run_slug: Optional[str] = Field(None, max_length=121, description="Existing outputs/ folder to resume")

    @field_validator("run_slug")
    @classmethod
    def _slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not SLUG_RE.match(v):
            raise ValueError("run_slug must be a saved run's folder name")
        return v

    @property
    def slug(self) -> str:
        return self.run_slug or slugify(self.company_name)

    @field_validator("company_name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("company_name must not be blank")
        return v

    @field_validator("context")
    @classmethod
    def _context(cls, v: Optional[str]) -> Optional[str]:
        return (v or "").strip() or None

    @field_validator("url")
    @classmethod
    def _url(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip()
        if v and (" " in v or "." not in v):
            raise ValueError("url should look like 'example.com' or 'https://example.com'")
        return v or None


class EventUI(PipelineUI):
    """Turns the pipeline's UI hooks into progress events instead of terminal output."""

    def __init__(self, emit: Callable[[dict[str, Any]], None]):
        super().__init__(Console(file=io.StringIO()))
        self.emit = emit
        self.current_stage = 0

    def banner(self, business: str, provider: str, model: str, search: list[str], out_dir: Path) -> None:
        self.emit({"type": "start", "business_name": business, "slug": out_dir.name, "provider": provider,
                   "model": model, "search_chain": search, "stages": STAGE_TITLES})

    def stage_start(self, stage: int, title: str) -> None:
        self.current_stage = stage
        self.emit({"type": "stage", "stage": stage, "title": title, "state": "active"})

    @contextmanager
    def agent(self, stage: int, title: str) -> Iterator[Callable[[str], None]]:
        self.emit({"type": "status", "stage": stage, "agent": title, "message": "starting…"})
        yield lambda message: self.emit({"type": "status", "stage": stage, "agent": title, "message": message})

    def agent_done(self, title: str, elapsed: float, totals: AgentTotals, files: list[Path]) -> None:
        self.emit({"type": "agent_done", "stage": self.current_stage, "agent": title, "seconds": round(elapsed, 1),
                   "input_tokens": totals.input_tokens, "output_tokens": totals.output_tokens,
                   "cost": fmt_cost(totals.cost_usd), "files": [f.name for f in files]})

    def stage_done(self, stage: int, title: str, elapsed: float) -> None:
        self.emit({"type": "stage", "stage": stage, "title": title, "state": "done", "seconds": round(elapsed, 1)})

    def skipped(self, stage: int, title: str) -> None:
        self.emit({"type": "stage", "stage": stage, "title": title, "state": "skipped"})

    def note(self, message: str) -> None:
        self.emit({"type": "note", "stage": self.current_stage, "message": message})

    def warn(self, message: str) -> None:
        self.note(message)

    def summary(self, *args: Any, **kwargs: Any) -> None:
        pass


def _claim(slug: str) -> None:
    with _active_lock:
        if slug in _active_runs:
            raise HTTPException(409, "An analysis for this company is already running.")
        _active_runs.add(slug)


def _release(slug: str) -> None:
    with _active_lock:
        _active_runs.discard(slug)


def _execute(req: AnalyzeRequest, ui: PipelineUI) -> dict[str, Any]:
    result = RUNNER(req.company_name, url=req.url, context=req.context, ui=ui,
                    build_prototype=req.include_prototype, from_step=req.from_stage, slug=req.run_slug)
    payload = report_payload(result.out_dir)
    total = result.tracker.total()
    payload["usage"] = {"input_tokens": total.input_tokens, "output_tokens": total.output_tokens,
                        "cost": fmt_cost(total.cost_usd)}
    return payload


def _error_message(exc: Exception) -> str:
    if isinstance(exc, (ConfigError, PipelineError, HandoffError, LLMError)):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/api/analyze/stream")
def analyze_stream(req: AnalyzeRequest) -> StreamingResponse:
    slug = req.slug
    _claim(slug)
    events: "queue.Queue[dict[str, Any] | None]" = queue.Queue()

    def work() -> None:
        try:
            events.put({"type": "result", **_execute(req, EventUI(events.put))})
        except Exception as exc:  # noqa: BLE001 - reported to the client as an event
            events.put({"type": "error", "message": _error_message(exc)})
        finally:
            _release(slug)
            events.put(None)

    threading.Thread(target=work, name=f"pipeline-{slug}", daemon=True).start()

    def stream() -> Iterator[str]:
        yield _sse({"type": "accepted", "slug": slug})
        while True:
            try:
                event = events.get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if event is None:
                return
            yield _sse(event)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    slug = req.slug
    _claim(slug)
    try:
        return _execute(req, EventUI(lambda _e: None))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        status = 400 if isinstance(exc, (ConfigError, PipelineError)) else 502
        raise HTTPException(status, _error_message(exc)) from exc
    finally:
        _release(slug)
