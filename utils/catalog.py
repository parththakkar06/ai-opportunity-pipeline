"""Curated vendor and compliance lists (data/vendors.yaml, data/compliance.yaml).

The strategist only sees, and may only name, entries from these files. Python then drops anything
else, so a vendor or a regulation can't be invented, and attaches each entry's official URL.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from utils.schemas import AIOpportunities, BusinessProfile, VendorRef

DATA = Path(__file__).resolve().parent.parent / "data"
INDIA = re.compile(r"\b(india|bengaluru|bangalore|mumbai|pune|delhi|gurugram|gurgaon|noida|hyderabad|chennai|kolkata|"
                   r"ahmedabad|kochi|thrissur|coimbatore|mysuru|gift city|maharashtra|karnataka|kerala|tamil nadu|"
                   r"telangana|gujarat)\b", re.I)
US = re.compile(r"\b(usa|united states|u\.s\.|[A-Z][a-z]+,\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|"
                r"ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY))\b")


@lru_cache(maxsize=4)
def _load(name: str) -> dict:
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8")) or {}


def market(profile: BusinessProfile) -> str:
    text = " ".join([profile.headquarters or "", *profile.geographic_presence])
    if INDIA.search(text):
        return "india"
    if US.search(text):
        return "us"
    return "global"


def vendors_for(mkt: str) -> list[VendorRef]:
    out = []
    for category, items in _load("vendors.yaml").items():
        for v in items:
            if "global" in v["markets"] or mkt in v["markets"]:
                out.append(VendorRef(name=v["name"], category=category, url=v["url"]))
    return out


def compliance_for(mkt: str) -> list[dict]:
    return list(_load("compliance.yaml").get(mkt, []))


def catalog_prompt(mkt: str) -> str:
    """The lists the strategist may choose from, grouped and compact."""
    by_cat: dict[str, list[str]] = {}
    for v in vendors_for(mkt):
        by_cat.setdefault(v.category, []).append(v.name)
    lines = [f"<vendor_catalog market=\"{mkt}\">"] + [f"{c}: {', '.join(n)}" for c, n in by_cat.items()]
    lines += ["</vendor_catalog>", "", f"<compliance_rules market=\"{mkt}\">"]
    rules = compliance_for(mkt)
    lines += [f"{r['id']}: {r['title']} (applies to: {', '.join(r['triggers'])}). {r['summary']}" for r in rules]
    if not rules:
        lines.append("none curated for this market; leave `compliance` empty")
    lines.append("</compliance_rules>")
    return "\n".join(lines)


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def apply_catalog(result: AIOpportunities, mkt: str) -> list[str]:
    """Drop vendors and compliance ids that aren't curated for this market; attach URLs. Returns notes."""
    vendors = {_key(v.name): v for v in vendors_for(mkt)}
    rules = {r["id"]: r for r in compliance_for(mkt)}
    notes = []
    for o in result.opportunities:
        if o.build_vs_buy:
            kept, refs = [], []
            for name in o.build_vs_buy.vendors:
                ref = vendors.get(_key(name))
                if ref and ref.name not in kept:
                    kept.append(ref.name)
                    refs.append(ref)
                elif not ref:
                    notes.append(f"{o.id}: dropped vendor '{name}' (not in data/vendors.yaml for {mkt})")
            o.build_vs_buy.vendors, o.build_vs_buy.vendor_refs = kept, refs
        cleaned = []
        for c in o.compliance:
            r = rules.get(c.rule_id)
            if r:
                cleaned.append(c.model_copy(update={"title": r["title"], "url": r["url"]}))
            else:
                notes.append(f"{o.id}: dropped compliance rule '{c.rule_id}' (not in data/compliance.yaml for {mkt})")
        o.compliance = cleaned
    return notes
