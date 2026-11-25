"""Phase 7 (evals) tests: similarity math, metrics from saved runs, cached judge, table and README output."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from run_pipeline import run_pipeline  # noqa: E402
from scripts.eval import main as eval_main  # noqa: E402
from tests.test_pipeline import FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.evals import (  # noqa: E402
    JUDGE_FILE, cosine, cross_company_similarity, judge_run, judge_weighted, load_runs, results_markdown,
    run_metrics, write_readme_section,
)

SYSTEM = (ROOT / "prompts" / "eval_judge.md").read_text()


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


@pytest.fixture
def outputs(tmp_path):
    for name in ("Maple Street Dental", "Cedar Dental Group"):
        run_pipeline(name, settings=settings(tmp_path), llm=FakeLLM(), research=FakeResearch(), ui=quiet_ui(),
                     build_prototype=False)
    (tmp_path / "half-done").mkdir()
    return tmp_path


def test_similarity_math():
    same = cross_company_similarity({"a": ["lead scoring for site visits"], "b": ["lead scoring for site visits"]})
    diff = cross_company_similarity({"a": ["lead scoring for site visits"], "b": ["dental chair no-show model"]})
    assert same["overall"] == pytest.approx(1.0, abs=1e-3) and diff["overall"] == 0
    three = cross_company_similarity({"a": ["x ray triage", "chair waitlist"], "b": ["chair waitlist"], "c": ["crane safety"]})
    assert three["pairs"] == 5                                    # only cross-company pairs are counted
    assert three["per_company"]["c"] == 0 and three["per_company"]["b"] > 0
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0) and cosine([1, 0], [0, 1]) == 0


def test_load_runs_and_metrics(outputs):
    runs, skipped = load_runs(outputs)
    assert [r.slug for r in runs] == ["cedar-dental-group", "maple-street-dental"]
    assert any(s.startswith("half-done") for s in skipped)
    m = run_metrics(runs[1])
    assert not runs[1].legacy and m["calls"] >= 10 and m["tokens_in"] > 0 and 0 <= m["pass_rate"] <= 1
    assert m["citations"] >= 1 and m["uncited"] == 1


def test_judge_is_one_call_then_cached(outputs):
    runs, _ = load_runs(outputs, ["maple-street-dental"])
    llm = FakeLLM()
    scores, cached = judge_run(runs[0], llm, "cheap", SYSTEM)
    assert not cached and llm.calls == ["JudgeScores"] and (runs[0].path / JUDGE_FILE).exists()
    assert judge_weighted(scores) == pytest.approx((8 * .3 + 7 * .2 + 8 * .2) / .7 * 10, abs=0.1)
    again, cached = judge_run(runs[0], llm, "cheap", SYSTEM)
    assert cached and llm.calls == ["JudgeScores"] and again == scores
    _s, cached = judge_run(runs[0], llm, "other-model", SYSTEM)     # a different judge model re-scores
    assert not cached and llm.calls.count("JudgeScores") == 2


def test_table_and_readme_block(outputs, tmp_path):
    runs, skipped = load_runs(outputs)
    sim = cross_company_similarity({r.slug: [o.title for o in r.report.ai_opportunities] for r in runs})
    md = results_markdown(runs, sim, "TF-IDF", {}, None, skipped)
    assert md.count("| current |") == 2 and "not run (pass `--judge`)" in md
    readme = tmp_path / "README.md"
    readme.write_text("# Project\n\nIntro.\n")
    assert write_readme_section(readme, "TABLE ONE\n")
    assert write_readme_section(readme, "TABLE TWO\n")
    text = readme.read_text()
    assert text.count("<!-- eval:start -->") == 1 and "TABLE TWO" in text and "TABLE ONE" not in text


def test_cli_end_to_end(outputs, tmp_path):
    out = tmp_path / "docs" / "eval_results.md"
    llm = FakeLLM()
    assert eval_main(["--outputs", str(outputs), "--judge", "--out", str(out)], llm=llm) == 0
    assert llm.calls == ["JudgeScores", "JudgeScores"]
    data = json.loads(out.with_suffix(".json").read_text())
    assert data["runs"]["maple-street-dental"]["judge_score"] > 0 and data["similarity"]["pairs"] > 0
    assert "Maple Street Dental" in out.read_text()
    empty = tmp_path / "empty-outputs"
    empty.mkdir()
    assert eval_main(["--outputs", str(empty), "--out", str(out)]) == 1     # nothing to evaluate
