from __future__ import annotations


def render_home_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>P26003 Commercial Invoice Recovery Assistant</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #f7f7f9; color: #222; }
    h1, h2 { margin: 0 0 12px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
    .card { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 14px; }
    label { display: block; margin-top: 8px; font-size: 13px; }
    input, select, textarea, button { width: 100%; margin-top: 4px; padding: 8px; box-sizing: border-box; }
    button { cursor: pointer; background: #0b5fff; color: #fff; border: 0; border-radius: 4px; margin-top: 12px; }
    pre { background: #111; color: #d7f5d7; padding: 10px; border-radius: 6px; overflow: auto; max-height: 260px; }
  </style>
</head>
<body>
  <h1>P26003 Commercial Invoice Recovery Assistant</h1>
  <p>Operational interface for intake, escalation, evidence, and tamper-evident audit review.</p>

  <div class="grid">
    <section class="card">
      <h2>Create Invoice</h2>
      <label>Invoice ID<input id="invoice_id" value="inv-ui-1" /></label>
      <label>Currency<input id="currency" value="GBP" /></label>
      <label>Principal Amount<input id="principal_amount" value="1200" /></label>
      <label>Issue Date<input id="issue_date" value="2026-01-01" /></label>
      <label>Due Date<input id="due_date" value="2026-01-31" /></label>
      <label>Jurisdiction
        <select id="jurisdiction">
          <option>ENGLAND_WALES</option><option>SCOTLAND</option><option>NORTHERN_IRELAND</option>
        </select>
      </label>
      <label>Debtor Type
        <select id="debtor_type">
          <option>LIMITED</option><option>SOLE_TRADER</option><option>INDIVIDUAL</option>
        </select>
      </label>
      <button onclick="createInvoice()">Create Invoice</button>
    </section>

    <section class="card">
      <h2>Escalate</h2>
      <label>Invoice ID<input id="esc_invoice_id" value="inv-ui-1" /></label>
      <label>Today<input id="esc_today" value="2026-02-10" /></label>
      <label>Current State
        <select id="esc_state">
          <option>ISSUED</option><option>FRIENDLY_REMINDER</option><option>OVERDUE_CHASER</option>
          <option>FORMAL_NOTICE</option><option>PRE_ACTION_PROTOCOL</option>
        </select>
      </label>
      <button onclick="escalate()">Run Escalation</button>
    </section>

    <section class="card">
      <h2>Upload Evidence</h2>
      <label>Invoice ID<input id="ev_invoice_id" value="inv-ui-1" /></label>
      <label>User ID<input id="ev_user_id" value="client-1" /></label>
      <label>Artifact Type
        <select id="ev_type">
          <option>CONTRACT</option><option>PROOF_OF_DELIVERY</option><option>PRE_ACTION_NOTICE</option><option>OTHER</option>
        </select>
      </label>
      <label>File<input id="ev_file" type="file" /></label>
      <button onclick="uploadEvidence()">Upload</button>
    </section>

    <section class="card">
      <h2>Generate Bundle / Manifest</h2>
      <label>Invoice ID<input id="out_invoice_id" value="inv-ui-1" /></label>
      <button onclick="generateBundle()">Generate Evidence Bundle</button>
      <button onclick="generateManifest()">Generate Manifest (JSON)</button>
      <button onclick="generateManifestPdf()">Generate Manifest (PDF)</button>
    </section>

    <section class="card">
      <h2>Late Payment Calculation</h2>
      <label>Invoice ID<input id="lp_invoice_id" value="inv-ui-1" /></label>
      <label>As Of Date<input id="lp_date" value="2026-03-15" /></label>
      <label>Commercial Transaction?
        <select id="lp_commercial"><option value="true">true</option><option value="false">false</option></select>
      </label>
      <label>Base Rate Override<input id="lp_rate" value="0.05" /></label>
      <button onclick="latePayment()">Calculate</button>
    </section>

    <section class="card">
      <h2>Review Audit & Artifacts</h2>
      <label>Invoice ID<input id="view_invoice_id" value="inv-ui-1" /></label>
      <button onclick="viewInvoice()">Get Invoice</button>
      <button onclick="viewArtifacts()">List Artifacts</button>
      <button onclick="viewEvents()">List Ledger Events</button>
    </section>
  </div>

  <h2 style="margin-top:18px;">Response</h2>
  <pre id="out">{}</pre>

  <script>
    const out = (v) => document.getElementById("out").textContent = JSON.stringify(v, null, 2);
    async function request(url, method, body, isForm) {
      const init = { method };
      if (body && !isForm) { init.headers = { "content-type": "application/json" }; init.body = JSON.stringify(body); }
      if (body && isForm) { init.body = body; }
      const r = await fetch(url, init);
      const j = await r.json();
      out({ status: r.status, body: j });
    }
    async function createInvoice() {
      await request("/invoices", "POST", {
        invoice_id: invoice_id.value, currency: currency.value, principal_amount: principal_amount.value,
        issue_date: issue_date.value, due_date: due_date.value, jurisdiction: jurisdiction.value, debtor_type: debtor_type.value
      });
    }
    async function escalate() {
      await request(`/invoices/${esc_invoice_id.value}/escalate`, "POST", {
        today: esc_today.value, current_state: esc_state.value
      });
    }
    async function uploadEvidence() {
      const f = ev_file.files[0];
      if (!f) { out({ error: "Select a file first." }); return; }
      const form = new FormData();
      form.append("user_id", ev_user_id.value);
      form.append("artifact_type", ev_type.value);
      form.append("file", f);
      await request(`/invoices/${ev_invoice_id.value}/evidence-artifacts`, "POST", form, true);
    }
    async function generateBundle() {
      await request(`/invoices/${out_invoice_id.value}/evidence-bundles`, "POST", {
        communications: ["Reminder sent"], formal_notices: ["Letter of Claim"], output_filename: "bundle.pdf"
      });
    }
    async function generateManifest() {
      await request(`/invoices/${out_invoice_id.value}/ledger-manifests`, "POST", {
        output_filename: "manifest.json", output_format: "json"
      });
    }
    async function generateManifestPdf() {
      await request(`/invoices/${out_invoice_id.value}/ledger-manifests`, "POST", {
        output_filename: "manifest.pdf", output_format: "pdf"
      });
    }
    async function latePayment() {
      await request(`/invoices/${lp_invoice_id.value}/late-payment-calculations`, "POST", {
        as_of_date: lp_date.value, is_commercial_transaction: lp_commercial.value === "true", base_rate_override: lp_rate.value
      });
    }
    async function viewInvoice() { await request(`/invoices/${view_invoice_id.value}`, "GET"); }
    async function viewArtifacts() { await request(`/invoices/${view_invoice_id.value}/evidence-artifacts`, "GET"); }
    async function viewEvents() { await request(`/invoices/${view_invoice_id.value}/ledger-events?limit=50`, "GET"); }
  </script>
</body>
</html>
"""

