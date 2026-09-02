from __future__ import annotations
#
# First Cairn Digital
# P26003 customer live shell and container runtime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from unpaid_invoice_escalator.api import create_app
from unpaid_invoice_escalator.customer_ui import (
    render_creditor_page_html,
    render_debtor_page_html,
    render_public_home_html,
)


PUBLIC_PAGE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "public, max-age=300",
}


def _public_html_response(html: str) -> HTMLResponse:
    return HTMLResponse(content=html, headers=PUBLIC_PAGE_HEADERS)


def create_live_app(core_app: FastAPI | None = None, **core_app_kwargs: object) -> FastAPI:
    mounted_core_app = core_app if core_app is not None else create_app(**core_app_kwargs)

    app = FastAPI(title="First Cairn Digital Live Shell")

    @app.get("/", response_class=HTMLResponse)
    def public_home() -> HTMLResponse:
        return _public_html_response(render_public_home_html())

    @app.get("/creditor", response_class=HTMLResponse)
    def public_creditor() -> HTMLResponse:
        return _public_html_response(render_creditor_page_html())

    @app.get("/debtor", response_class=HTMLResponse)
    def public_debtor() -> HTMLResponse:
        return _public_html_response(render_debtor_page_html())

    app.mount("", mounted_core_app)
    return app


app = create_live_app()


def main() -> None:
    import uvicorn

    uvicorn.run("unpaid_invoice_escalator.live_app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
