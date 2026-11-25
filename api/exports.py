"""Export endpoints: build files from a saved run on request (no LLM calls; works in demo mode).

GET /api/examples/{slug}/export/pptx | report.pdf | pitch.pdf | email | eml | zip
The email endpoints take an optional ?to= (empty by default). Nothing is ever sent.
"""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from utils.io import HandoffError
from utils.export.data import ExportData, load
from utils.export.documents import (
    FILES, build_all, deck_pptx, email_draft, eml_bytes, gmail_url, mailto_url, pitch_pdf, report_pdf, zip_bytes,
)
from utils.export.pdf import PDFUnavailable

router = APIRouter()
_run_dir: Callable | None = None      # set by api.index (avoids a circular import)
TYPES = {"pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
         "pdf": "application/pdf", "eml": "message/rfc822", "zip": "application/zip"}


def _data(slug: str) -> ExportData:
    try:
        return load(_run_dir(slug))
    except HandoffError as exc:
        raise HTTPException(404, str(exc)) from exc


def _file(data: bytes, filename: str, kind: str) -> Response:
    return Response(data, media_type=TYPES[kind],
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


def _guard(fn):
    try:
        return fn()
    except PDFUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/api/examples/{slug}/export/email")
def export_email(slug: str, to: str = Query("", max_length=320)) -> dict:
    d = _data(slug)
    draft = _guard(lambda: email_draft(d))
    url, cut = mailto_url(draft["subject"], draft["body"], to)
    return {**draft, "to": to, "gmail_url": gmail_url(draft["subject"], draft["body"], to), "mailto_url": url,
            "mailto_shortened": cut}


@router.get("/api/examples/{slug}/export/{kind}")
def export_file(slug: str, kind: str, to: str = Query("", max_length=320)) -> Response:
    d = _data(slug)
    if kind == "pptx":
        return _file(_guard(lambda: deck_pptx(d)), f"{slug}-{FILES['pptx'][3:]}", "pptx")
    if kind == "report.pdf":
        return _file(_guard(lambda: report_pdf(d))[0], f"{slug}-report.pdf", "pdf")
    if kind == "pitch.pdf":
        return _file(_guard(lambda: pitch_pdf(d))[0], f"{slug}-pitch.pdf", "pdf")
    if kind == "eml":
        return _file(_guard(lambda: eml_bytes(d, pitch_pdf(d)[0], to)), f"{slug}-outreach.eml", "eml")
    if kind == "zip":
        return _file(_guard(lambda: zip_bytes(build_all(d))), f"{slug}-exports.zip", "zip")
    raise HTTPException(404, "Unknown export. Use pptx, report.pdf, pitch.pdf, email, eml or zip.")
