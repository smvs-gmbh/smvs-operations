"""Standalone local UI prototype: fictional data, no database or external services."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

ASSETS = Path(__file__).parent / "assets"
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def preview_headers(request, call_next):
    response = await call_next(request)
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'",
        }
    )
    return response


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ASSETS / "index.html", media_type="text/html")


@app.get("/preview.css", include_in_schema=False)
def css():
    return FileResponse(ASSETS / "preview.css", media_type="text/css")


@app.get("/preview.js", include_in_schema=False)
def javascript():
    return FileResponse(ASSETS / "preview.js", media_type="text/javascript")


@app.get("/proposal", include_in_schema=False)
def proposal():
    return FileResponse(ASSETS / "proposal.html", media_type="text/html")


@app.get("/proposal.css", include_in_schema=False)
def proposal_css():
    return FileResponse(ASSETS / "proposal.css", media_type="text/css")


@app.get("/proposal.js", include_in_schema=False)
def proposal_javascript():
    return FileResponse(ASSETS / "proposal.js", media_type="text/javascript")


@app.get("/case-study", include_in_schema=False)
def case_study():
    return FileResponse(ASSETS / "case-study.html", media_type="text/html")


@app.get("/case-study.css", include_in_schema=False)
def case_study_css():
    return FileResponse(ASSETS / "case-study.css", media_type="text/css")


@app.get("/case-study.js", include_in_schema=False)
def case_study_javascript():
    return FileResponse(ASSETS / "case-study.js", media_type="text/javascript")


@app.get("/focused", include_in_schema=False)
def focused():
    return FileResponse(ASSETS / "focused.html", media_type="text/html")


@app.get("/focused.css", include_in_schema=False)
def focused_css():
    return FileResponse(ASSETS / "focused.css", media_type="text/css")


@app.get("/focused.js", include_in_schema=False)
def focused_javascript():
    return FileResponse(ASSETS / "focused.js", media_type="text/javascript")


@app.get("/compact", include_in_schema=False)
def compact():
    return FileResponse(ASSETS / "compact.html", media_type="text/html")


@app.get("/compact.css", include_in_schema=False)
def compact_css():
    return FileResponse(ASSETS / "compact.css", media_type="text/css")


@app.get("/compact.js", include_in_schema=False)
def compact_javascript():
    return FileResponse(ASSETS / "compact.js", media_type="text/javascript")


@app.get("/columns", include_in_schema=False)
def columns():
    return FileResponse(ASSETS / "columns.html", media_type="text/html")


@app.get("/columns.css", include_in_schema=False)
def columns_css():
    return FileResponse(ASSETS / "columns.css", media_type="text/css")


@app.get("/columns.js", include_in_schema=False)
def columns_javascript():
    return FileResponse(ASSETS / "columns.js", media_type="text/javascript")


@app.get("/alerts", include_in_schema=False)
def alerts():
    return FileResponse(ASSETS / "alerts.html", media_type="text/html")


@app.get("/alerts.css", include_in_schema=False)
def alerts_css():
    return FileResponse(ASSETS / "alerts.css", media_type="text/css")


@app.get("/alerts.js", include_in_schema=False)
def alerts_javascript():
    return FileResponse(ASSETS / "alerts.js", media_type="text/javascript")
