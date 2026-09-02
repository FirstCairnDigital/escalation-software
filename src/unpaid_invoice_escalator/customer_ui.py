from __future__ import annotations
#
# First Cairn Digital
# P26003 customer live shell and container runtime

from html import escape as html_escape


PUBLIC_PAGE_STYLES = """
:root {
  --bg: #f3f6fb;
  --panel: #ffffff;
  --panel-soft: #f8fbff;
  --text: #172033;
  --muted: #5f6f85;
  --line: #d9e4f2;
  --brand: #173c7a;
  --brand-strong: #0d2347;
  --brand-soft: #e8f0ff;
  --accent: #2d67ff;
  --accent-strong: #1747be;
  --success: #177a52;
  --warn: #a65a00;
  --shadow: 0 18px 42px rgba(15, 23, 42, 0.10);
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background: linear-gradient(180deg, #f7f9fd 0%, #eef4fb 100%);
  color: var(--text);
  font-family: Arial, sans-serif;
}
body { min-height: 100vh; }
a { color: var(--accent-strong); }
a:focus-visible,
button:focus-visible,
input:focus-visible {
  outline: 3px solid #ffbf47;
  outline-offset: 2px;
}
.shell {
  max-width: 1160px;
  margin: 0 auto;
  padding: 24px 18px 48px;
}
.masthead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 28px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}
.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--brand), #2f66d0);
  color: #fff;
  font-weight: 700;
}
.brand-copy strong {
  display: block;
  font-size: 17px;
}
.brand-copy span {
  display: block;
  color: var(--muted);
  margin-top: 4px;
  font-size: 13px;
}
.nav {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.nav a {
  text-decoration: none;
  color: var(--brand-strong);
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 10px 14px;
}
.hero,
.panel,
.journey-card,
.notice-card {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid var(--line);
  border-radius: 24px;
  box-shadow: var(--shadow);
}
.hero {
  padding: 34px;
  display: grid;
  gap: 22px;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--brand-soft);
  color: var(--brand);
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 700;
}
.hero h1,
.panel h1,
.panel h2,
.journey-card h2,
.notice-card h2 {
  margin: 0;
  color: var(--brand-strong);
}
.hero h1 {
  font-size: 40px;
  line-height: 1.1;
  max-width: 16ch;
}
.lede,
.panel p,
.journey-card p,
.notice-card p,
li {
  color: var(--text);
  line-height: 1.6;
}
.lede {
  max-width: 72ch;
  font-size: 18px;
}
.hero-actions,
.journeys,
.grid-2 {
  display: grid;
  gap: 16px;
}
.journeys,
.grid-2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.button-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.button,
.button-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 46px;
  padding: 0 18px;
  border-radius: 14px;
  font-weight: 700;
  text-decoration: none;
  border: 1px solid transparent;
}
.button {
  background: var(--accent);
  color: #fff;
}
.button-secondary {
  background: #fff;
  border-color: var(--line);
  color: var(--brand-strong);
}
.journey-card,
.notice-card,
.panel {
  padding: 26px;
}
.journey-card ul,
.notice-card ul,
.panel ul {
  margin: 14px 0 0;
  padding-left: 20px;
}
.section-title {
  margin: 0 0 14px;
  font-size: 24px;
}
.kicker {
  color: var(--muted);
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.08em;
  font-weight: 700;
  margin-bottom: 10px;
}
.meta-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.meta-strip .panel {
  padding: 18px;
}
.meta-strip strong {
  display: block;
  margin-bottom: 8px;
  color: var(--brand);
}
form {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}
label {
  display: grid;
  gap: 8px;
  font-weight: 700;
  color: var(--brand-strong);
}
input {
  min-height: 46px;
  border-radius: 14px;
  border: 1px solid #b9c9df;
  padding: 11px 14px;
  font: inherit;
  background: #fff;
  color: var(--text);
}
.helper {
  color: var(--muted);
  font-size: 14px;
  margin: 0;
}
.footer-note {
  margin-top: 28px;
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.86);
  color: var(--muted);
  line-height: 1.6;
}
@media (max-width: 840px) {
  .masthead {
    align-items: flex-start;
    flex-direction: column;
  }
  .hero h1 {
    font-size: 32px;
  }
  .journeys,
  .grid-2,
  .meta-strip {
    grid-template-columns: 1fr;
  }
}
"""


def _page_template(*, title: str, summary: str, body: str) -> str:
    return (
        "<!doctype html>"
        "<html lang=\"en\">"
        "<head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{html_escape(title)}</title>"
        f"<meta name=\"description\" content=\"{html_escape(summary)}\">"
        f"<style>{PUBLIC_PAGE_STYLES}</style>"
        "</head>"
        "<body>"
        "<div class=\"shell\">"
        "<header class=\"masthead\">"
        "<div class=\"brand\">"
        "<div class=\"brand-mark\" aria-hidden=\"true\">FCD</div>"
        "<div class=\"brand-copy\">"
        "<strong>First Cairn Digital</strong>"
        "<span>B2B unpaid-invoice resolution workflows</span>"
        "</div>"
        "</div>"
        "<nav class=\"nav\" aria-label=\"Public navigation\">"
        "<a href=\"/\">Home</a>"
        "<a href=\"/creditor\">For creditors</a>"
        "<a href=\"/debtor\">For debtors</a>"
        "</nav>"
        "</header>"
        f"{body}"
        "<div class=\"footer-note\">"
        "First Cairn Digital supports staged commercial invoice-resolution workflows. "
        "It is not presented here as a solicitor, court, debt collection agency, or litigation representative. "
        "Real customer production use still requires stronger production infrastructure and human authentication controls."
        "</div>"
        "</div>"
        "</body>"
        "</html>"
    )


def render_public_home_html() -> str:
    return _page_template(
        title="First Cairn Digital | B2B invoice resolution",
        summary="Customer journeys for creditors and debtors using First Cairn Digital B2B unpaid-invoice resolution workflows.",
        body="""
<main class="hero">
  <div class="eyebrow">B2B unpaid-invoice resolution across England &amp; Wales, Scotland, and Northern Ireland</div>
  <div class="hero-actions">
    <h1>Resolution first. Evidence ready when needed.</h1>
    <p class="lede">
      First Cairn Digital supports staged business-to-business unpaid-invoice resolution workflows.
      The process is progressive, factual, and designed to help a creditor recover a valid debt while
      making it harder to pursue an invalid one.
    </p>
    <div class="button-row">
      <a class="button" href="/creditor">I am owed money</a>
      <a class="button-secondary" href="/debtor">I have received a notice</a>
    </div>
  </div>
</main>
<section class="journeys" aria-label="Customer journeys" style="margin-top: 22px;">
  <article class="journey-card">
    <div class="kicker">Creditor journey</div>
    <h2>I am owed money</h2>
    <p>
      Prepare a business invoice case, review invoice health, upload supporting evidence, and move
      through staged actions with clear pricing shown before any chargeable commitment.
    </p>
    <ul>
      <li>Submit an unpaid business invoice and supporting records.</li>
      <li>See staged actions and First Cairn Digital charges before committing.</li>
      <li>Stop between stages where the workflow permits.</li>
      <li>Review debtor responses, payments, payment plans, and settlement proposals.</li>
    </ul>
    <p><a href="/creditor">Explore the creditor route</a></p>
  </article>
  <article class="journey-card">
    <div class="kicker">Debtor journey</div>
    <h2>I have received a notice</h2>
    <p>
      Verify that a communication is genuine and, once verified, respond through structured options
      such as questions, disputes, payment updates, payment plans, or settlement dialogue.
    </p>
    <ul>
      <li>Verify the notice using a case reference and code.</li>
      <li>Confirm payment, provide a payment date, or raise a concern.</li>
      <li>Challenge information or dispute part or all of a claim.</li>
      <li>Engage with payment-plan or settlement options where available.</li>
    </ul>
    <p><a href="/debtor">Go to notice verification</a></p>
  </article>
</section>
<section class="meta-strip" aria-label="Product overview" style="margin-top: 22px;">
  <div class="panel">
    <strong>Staged process</strong>
    <span>The workflow is structured in stages rather than defaulting immediately to court escalation.</span>
  </div>
  <div class="panel">
    <strong>Transparent commitment</strong>
    <span>Chargeable creditor actions are shown before commitment rather than hidden behind a later surprise fee.</span>
  </div>
  <div class="panel">
    <strong>Product boundary</strong>
    <span>This public shell is for direct B2B trade invoices only, not consumer credit or general debt collection.</span>
  </div>
</section>
""",
    )


def render_creditor_page_html() -> str:
    return _page_template(
        title="For creditors | First Cairn Digital",
        summary="Information for creditors using First Cairn Digital B2B unpaid-invoice resolution workflows.",
        body="""
<main class="grid-2" aria-label="Creditor overview">
  <section class="panel">
    <div class="kicker">For creditors</div>
    <h1>Prepare and progress a business invoice case</h1>
    <p>
      First Cairn Digital supports businesses administering their own direct commercial trade-invoice
      recovery workflow. It helps organise the claim, evidence, responses, and staged decisions.
    </p>
    <ul>
      <li>Submit an unpaid business invoice.</li>
      <li>Upload supporting evidence such as contracts, purchase orders, and delivery records.</li>
      <li>Run a case-health review before escalation progresses.</li>
      <li>See staged actions and prices before any chargeable commitment.</li>
      <li>Track debtor questions, payments, payment plans, and settlement proposals.</li>
      <li>Download evidence and handoff-ready records as the case develops.</li>
    </ul>
    <div class="button-row" style="margin-top: 18px;">
      <a class="button" href="/">Back to home</a>
      <a class="button-secondary" href="/health">Technical health check</a>
    </div>
  </section>
  <section class="panel">
    <div class="kicker">Next phase</div>
    <h2>Human sign-in and case start</h2>
    <p>
      Human creditor sign-in is planned for a later phase. This page therefore describes the intended
      creditor journey without exposing internal staff tools or pretending that public sign-in is already live.
    </p>
    <p>
      When enabled, the intended journey will support starting a case, reviewing staged actions, and
      deciding whether to proceed, pause, or stop where the workflow permits.
    </p>
    <p class="helper">
      This public page does not link directly to internal operations, compliance, or administration surfaces.
    </p>
  </section>
</main>
""",
    )


def render_debtor_page_html() -> str:
    return _page_template(
        title="Verify a notice | First Cairn Digital",
        summary="Verify a First Cairn Digital case notice and understand available debtor response options.",
        body="""
<main class="grid-2" aria-label="Debtor notice verification">
  <section class="notice-card">
    <div class="kicker">Verify a notice</div>
    <h1>Check that a communication is genuine</h1>
    <p>
      Enter the case reference and verification code shown in the communication to confirm that the
      notice is genuine before taking any further action.
    </p>
    <form action="/verify" method="get">
      <label for="case">Case reference
        <input id="case" name="case" type="text" inputmode="text" autocomplete="off" required>
      </label>
      <label for="code">Verification code
        <input id="code" name="code" type="text" inputmode="text" autocomplete="off" required>
      </label>
      <p class="helper">Verification uses the existing First Cairn Digital notice-check route.</p>
      <div class="button-row">
        <button class="button" type="submit">Verify notice</button>
        <a class="button-secondary" href="/">Back to home</a>
      </div>
    </form>
  </section>
  <section class="notice-card">
    <div class="kicker">After verification</div>
    <h2>Available case actions in plain language</h2>
    <p>
      Once a case is verified, the available options may include:
    </p>
    <ul>
      <li>tell us it has already been paid;</li>
      <li>ask a question about the invoice;</li>
      <li>challenge inaccurate information;</li>
      <li>dispute some or all of the claim;</li>
      <li>give a payment date;</li>
      <li>propose a payment plan;</li>
      <li>make or respond to a settlement offer where available.</li>
    </ul>
    <p class="helper">
      This page does not expose creditor or administrator controls.
    </p>
  </section>
</main>
""",
    )
