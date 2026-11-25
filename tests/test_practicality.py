"""Phase 5 (practicality) tests: curated vendors and compliance, schema checks, pipeline output."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
import yaml  # noqa: E402

from agents.base import OPPORTUNITIES_JSON  # noqa: E402
from agents.report import build_report, render_report_markdown  # noqa: E402
from agents.strategist import check_opportunities  # noqa: E402
from run_pipeline import run_pipeline  # noqa: E402
from tests.test_pipeline import BUSINESS, FIXTURES, FakeLLM, FakeResearch, quiet_ui, settings  # noqa: E402
from utils.catalog import DATA, apply_catalog, catalog_prompt, compliance_for, market, vendors_for  # noqa: E402
from utils.schemas import AIOpportunities, BusinessProfile  # noqa: E402


@pytest.fixture(autouse=True)
def _prices(monkeypatch):
    monkeypatch.setenv("PRICE_INPUT_PER_MTOK", "1.0")
    monkeypatch.setenv("PRICE_OUTPUT_PER_MTOK", "2.0")


def opps() -> AIOpportunities:
    return AIOpportunities.model_validate_json((FIXTURES / "AIOpportunities.json").read_text())


def profile(**over) -> BusinessProfile:
    data = json.loads((FIXTURES / "BusinessProfileDraft.json").read_text())
    data.update(over)
    return BusinessProfile.model_validate(data)


# ------------------------------------------------------------------------------------------- curated files
def test_curated_files_are_well_formed():
    vendors = yaml.safe_load((DATA / "vendors.yaml").read_text())
    for category, items in vendors.items():
        for v in items:
            assert v["url"].startswith("https://") and v["markets"] and v["name"], (category, v)
    rules = yaml.safe_load((DATA / "compliance.yaml").read_text())
    ids = [r["id"] for rs in rules.values() for r in rs]
    assert len(ids) == len(set(ids))
    assert {"dpdp-2023", "rera-advertising", "trai-dlt"} <= set(ids)
    for rs in rules.values():
        for r in rs:
            assert r["url"].startswith("https://") and r["summary"] and r["triggers"]


@pytest.mark.parametrize("hq,presence,expected", [
    ("Bengaluru, Karnataka", ["Bengaluru", "Pune"], "india"),
    ("Austin, TX", ["Austin, TX"], "us"),
    ("Dubai", ["UAE"], "global"),
])
def test_market_detection(hq, presence, expected):
    assert market(profile(headquarters=hq, geographic_presence=presence)) == expected


def test_market_scoped_lists():
    india = {v.name for v in vendors_for("india")}
    us = {v.name for v in vendors_for("us")}
    assert {"LeadSquared", "Sell.Do", "WhatsApp Business Platform", "Salesforce"} <= india
    assert "LeadSquared" not in us and "Open Dental" in us and "Open Dental" not in india
    assert [r["id"] for r in compliance_for("global")] == []
    text = catalog_prompt("india")
    assert "<vendor_catalog" in text and "dpdp-2023" in text and "Sell.Do" in text


# ------------------------------------------------------------------------------------------- filtering
def test_vendors_not_in_the_curated_list_are_dropped():
    result = opps()
    notes = apply_catalog(result, "us")
    o1 = result.opportunities[0]
    assert o1.build_vs_buy.vendors == ["Open Dental", "Twilio"]
    assert [v.url for v in o1.build_vs_buy.vendor_refs] == ["https://www.opendental.com", "https://www.twilio.com"]
    assert any("DentalBot Pro" in n for n in notes)


def test_vendor_names_match_loosely_but_markets_strictly():
    result = opps()
    result.opportunities[0].build_vs_buy.vendors = ["sell.do", "SALESFORCE", "Salesforce"]
    apply_catalog(result, "india")
    assert result.opportunities[0].build_vs_buy.vendors == ["Sell.Do", "Salesforce"]
    result.opportunities[0].build_vs_buy.vendors = ["Sell.Do"]
    apply_catalog(result, "us")
    assert result.opportunities[0].build_vs_buy.vendors == []


def test_compliance_ids_are_filtered_and_enriched():
    result = opps()
    notes = apply_catalog(result, "us")
    c = result.opportunities[0].compliance
    assert [x.rule_id for x in c] == ["hipaa", "tcpa"]
    assert c[0].title.startswith("HIPAA") and c[0].url.startswith("https://www.hhs.gov")
    assert any("'gdpr'" in n for n in notes)
    result = opps()
    apply_catalog(result, "india")                       # US rules don't apply to an Indian company
    assert all(not o.compliance for o in result.opportunities)


# ------------------------------------------------------------------------------------------- schema checks
def test_check_requires_practicality_fields():
    result = opps()
    assert check_opportunities(result) is None
    result.opportunities[0].pilot_30_60_90 = result.opportunities[0].pilot_30_60_90[:2]
    result.opportunities[1].build_vs_buy = None
    result.opportunities[2].data_readiness = []
    problem = check_opportunities(result)
    assert "opp-1 needs pilot_30_60_90" in problem and "opp-2 needs build_vs_buy" in problem
    assert "opp-3 needs data_readiness" in problem


def test_older_opportunities_without_practicality_still_load():
    data = json.loads((FIXTURES / "AIOpportunities.json").read_text())
    for o in data["opportunities"]:
        for k in ("build_vs_buy", "pilot_30_60_90", "data_readiness", "compliance"):
            o.pop(k)
    loaded = AIOpportunities.model_validate(data)
    assert loaded.opportunities[0].build_vs_buy is None and loaded.opportunities[0].pilot_30_60_90 == []


# ------------------------------------------------------------------------------------------- pipeline
def test_pipeline_saves_filtered_practical_plan_and_report_shows_it(tmp_path):
    llm = FakeLLM()
    run_pipeline(BUSINESS, settings=settings(tmp_path), llm=llm, research=FakeResearch(), ui=quiet_ui(),
                 build_prototype=False)
    out = tmp_path / "maple-street-dental"
    saved = AIOpportunities.model_validate_json((out / OPPORTUNITIES_JSON).read_text())
    all_vendors = {v for o in saved.opportunities for v in o.build_vs_buy.vendors}
    assert "DentalBot Pro" not in all_vendors and "Open Dental" in all_vendors
    assert all(c.rule_id != "gdpr" for o in saved.opportunities for c in o.compliance)
    assert '<vendor_catalog market="us">' in llm.prompts["AIOpportunities"]
    report = build_report(out)
    top = report.ai_opportunities[0]
    assert top.build_vs_buy and len(top.pilot_30_60_90) == 3 and top.data_readiness
    md = render_report_markdown(report)
    assert "**30/60/90-day pilot:**" in md and "[Open Dental](https://www.opendental.com)" in md
    assert "[HIPAA Privacy and Security Rules](https://www.hhs.gov/hipaa/index.html)" in md
