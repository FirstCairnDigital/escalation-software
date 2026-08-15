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
  <label style="max-width:420px;">API Key (for secured environments)<input id="api_key" value="" placeholder="Paste x-api-key value" /></label>

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
      <button onclick="verifyManifest()">Verify Manifest (manifest.json)</button>
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
      <h2>Pre-Overdue Contract Hygiene</h2>
      <label>Invoice ID<input id="hy_invoice_id" value="inv-ui-1" /></label>
      <label>Creditor Legal Entity<input id="hy_creditor_name" value="First Cairn Digital Ltd" /></label>
      <label>Creditor Companies House Number<input id="hy_creditor_ch" value="SC123456" placeholder="e.g. SC123456 or 12345678" /></label>
      <label>Creditor VAT Number<input id="hy_creditor_vat" value="GB123456789" placeholder="e.g. GB123456789" /></label>
      <label>Creditor Trading Address<input id="hy_creditor_addr" value="1 Example Street, Glasgow" /></label>
      <label>Debtor Legal Entity<input id="hy_debtor_name" value="Example Buyer Ltd" /></label>
      <label>Debtor Companies House Number<input id="hy_debtor_ch" value="NI654321" placeholder="e.g. NI654321 or 87654321" /></label>
      <label>Debtor VAT Number<input id="hy_debtor_vat" value="GB987654321" placeholder="e.g. GB987654321" /></label>
      <label>Debtor Trading Address<input id="hy_debtor_addr" value="2 Sample Road, Belfast" /></label>
      <label>PO Required?
        <select id="hy_po_required"><option value="false">false</option><option value="true">true</option></select>
      </label>
      <label>PO Reference<input id="hy_po_ref" value="" /></label>
      <label>Payment Terms Days<input id="hy_terms" value="30" /></label>
      <label>Contractual Interest Clause?
        <select id="hy_interest"><option value="true">true</option><option value="false">false</option></select>
      </label>
      <label>Contractual Recovery Clause?
        <select id="hy_recovery"><option value="true">true</option><option value="false">false</option></select>
      </label>
      <label>Proof of Delivery Required?
        <select id="hy_pod"><option value="true">true</option><option value="false">false</option></select>
      </label>
      <label>Suggested Clause Text (optional)<textarea id="hy_clause">Late-payment clause draft.</textarea></label>
      <label>Notes<textarea id="hy_notes"></textarea></label>
      <button onclick="recordHygiene()">Record Hygiene Check</button>
      <button onclick="listHygiene()">List Hygiene Checks</button>
    </section>

    <section class="card">
      <h2>Review Audit & Artifacts</h2>
      <label>Invoice ID<input id="view_invoice_id" value="inv-ui-1" /></label>
      <label>Artifact Type Filter
        <select id="view_artifact_type">
          <option value="">(all)</option>
          <option>CONTRACT</option><option>PROOF_OF_DELIVERY</option><option>PRE_ACTION_NOTICE</option><option>OTHER</option>
        </select>
      </label>
      <label>Artifact Limit<input id="view_artifact_limit" value="100" /></label>
      <label>Artifact Offset<input id="view_artifact_offset" value="0" /></label>
      <label>Event Type Filter<input id="view_event_type" value="" /></label>
      <label>Event Limit<input id="view_event_limit" value="50" /></label>
      <label>Event Offset<input id="view_event_offset" value="0" /></label>
      <button onclick="viewInvoice()">Get Invoice</button>
      <button onclick="viewArtifacts()">List Artifacts</button>
      <button onclick="viewEvents()">List Ledger Events</button>
      <button onclick="openWorkspace()">Open Invoice Workspace</button>
    </section>
  </div>

  <h2 style="margin-top:18px;">Response</h2>
  <pre id="out">{}</pre>

  <script>
    const out = (v) => document.getElementById("out").textContent = JSON.stringify(v, null, 2);
    const authHeaders = () => {
      const key = (document.getElementById("api_key")?.value || "").trim();
      return key ? { "x-api-key": key } : {};
    };
    async function request(url, method, body, isForm) {
      const init = { method };
      if (body && !isForm) { init.headers = { ...authHeaders(), "content-type": "application/json" }; init.body = JSON.stringify(body); }
      if (!body) { init.headers = authHeaders(); }
      if (body && isForm) { init.headers = authHeaders(); init.body = body; }
      try {
        const r = await fetch(url, init);
        let j = null;
        try {
          j = await r.json();
        } catch {
          j = { detail: await r.text() };
        }
        out({ status: r.status, body: j });
      } catch (error) {
        out({ status: "network_error", body: { detail: String(error) } });
      }
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
    async function verifyManifest() {
      await request(`/invoices/${out_invoice_id.value}/ledger-manifests/verify`, "POST", {
        output_filename: "manifest.json"
      });
    }
    async function latePayment() {
      await request(`/invoices/${lp_invoice_id.value}/late-payment-calculations`, "POST", {
        as_of_date: lp_date.value, is_commercial_transaction: lp_commercial.value === "true", base_rate_override: lp_rate.value
      });
    }
    async function recordHygiene() {
      await request(`/invoices/${hy_invoice_id.value}/pre-overdue-hygiene`, "POST", {
        creditor_legal_entity_name: hy_creditor_name.value,
        creditor_companies_house_number: hy_creditor_ch.value,
        creditor_vat_number: hy_creditor_vat.value,
        creditor_trading_address: hy_creditor_addr.value,
        debtor_legal_entity_name: hy_debtor_name.value,
        debtor_companies_house_number: hy_debtor_ch.value,
        debtor_vat_number: hy_debtor_vat.value,
        debtor_trading_address: hy_debtor_addr.value,
        po_required: hy_po_required.value === "true",
        po_reference: hy_po_ref.value || null,
        payment_terms_days: Number(hy_terms.value || "0"),
        contractual_interest_clause_present: hy_interest.value === "true",
        contractual_recovery_clause_present: hy_recovery.value === "true",
        proof_of_delivery_required: hy_pod.value === "true",
        suggested_clause_text: hy_clause.value || null,
        notes: hy_notes.value || ""
      });
    }
    async function listHygiene() { await request(`/invoices/${hy_invoice_id.value}/pre-overdue-hygiene`, "GET"); }
    async function viewInvoice() { await request(`/invoices/${view_invoice_id.value}`, "GET"); }
    async function viewArtifacts() {
      const params = new URLSearchParams();
      if (view_artifact_type.value) params.set("artifact_type", view_artifact_type.value);
      params.set("limit", view_artifact_limit.value || "100");
      params.set("offset", view_artifact_offset.value || "0");
      await request(`/invoices/${view_invoice_id.value}/evidence-artifacts?${params.toString()}`, "GET");
    }
    async function viewEvents() {
      const params = new URLSearchParams();
      if (view_event_type.value) params.set("event_type", view_event_type.value);
      params.set("limit", view_event_limit.value || "50");
      params.set("offset", view_event_offset.value || "0");
      await request(`/invoices/${view_invoice_id.value}/ledger-events?${params.toString()}`, "GET");
    }
    function openWorkspace() {
      window.location.href = `/ui/invoices/${encodeURIComponent(view_invoice_id.value)}`;
    }
  </script>
</body>
</html>
"""


def render_invoice_workspace_html(invoice_id: str) -> str:
    template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Invoice Workspace</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; background: #f7f7f9; color: #222; }
    .header { display: flex; justify-content: space-between; align-items: center; }
    .tabs { display: flex; gap: 8px; margin: 16px 0; flex-wrap: wrap; }
    .tab { border: 1px solid #bbb; background: #fff; padding: 8px 12px; border-radius: 6px; cursor: pointer; }
    .tab.active { background: #0b5fff; color: #fff; border-color: #0b5fff; }
    .panel { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 14px; }
    input, select, button { padding: 8px; margin: 4px 0; }
    button { cursor: pointer; background: #0b5fff; color: #fff; border: 0; border-radius: 4px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
    pre { background: #111; color: #d7f5d7; padding: 10px; border-radius: 6px; overflow: auto; max-height: 520px; }
  </style>
</head>
<body>
  <div class="header">
    <h1>Invoice Workspace: <span id="invoice_id_label"></span></h1>
    <a href="/">Back to Home UI</a>
  </div>
  <label style="max-width:420px;">API Key (for secured environments)<input id="api_key" value="" placeholder="Paste x-api-key value" /></label>

  <div class="tabs">
    <button id="tab-summary" class="tab active" onclick="loadTab('summary')">Summary</button>
    <button id="tab-evidence" class="tab" onclick="loadTab('evidence')">Evidence</button>
    <button id="tab-ledger" class="tab" onclick="loadTab('ledger')">Ledger</button>
    <button id="tab-hygiene" class="tab" onclick="loadTab('hygiene')">Hygiene</button>
    <button id="tab-actions" class="tab" onclick="loadTab('actions')">Actions</button>
  </div>

  <div id="panel" class="panel"></div>
  <h3>Response</h3>
  <pre id="out">{}</pre>

  <script>
    const invoiceId = "__INVOICE_ID__";
    document.getElementById("invoice_id_label").textContent = invoiceId;
    const out = (v) => document.getElementById("out").textContent = JSON.stringify(v, null, 2);
    const panel = document.getElementById("panel");
    const authHeaders = () => {
      const key = (document.getElementById("api_key")?.value || "").trim();
      return key ? { "x-api-key": key } : {};
    };

    async function request(url, method, body, isForm) {
      const init = { method };
      if (body && !isForm) { init.headers = { ...authHeaders(), "content-type": "application/json" }; init.body = JSON.stringify(body); }
      if (!body) { init.headers = authHeaders(); }
      if (body && isForm) { init.headers = authHeaders(); init.body = body; }
      try {
        const r = await fetch(url, init);
        let j = null;
        try {
          j = await r.json();
        } catch {
          j = { detail: await r.text() };
        }
        out({ status: r.status, body: j });
        return j;
      } catch (error) {
        const networkError = { status: "network_error", body: { detail: String(error) } };
        out(networkError);
        return networkError;
      }
    }

    function setActive(tabName) {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.getElementById(`tab-${tabName}`).classList.add("active");
    }

    async function loadTab(tabName) {
      setActive(tabName);
      if (tabName === "summary") {
        panel.innerHTML = `<button onclick="viewSummary()">Refresh Summary</button>`;
        await viewSummary();
        return;
      }
      if (tabName === "evidence") {
        panel.innerHTML = `
          <div class="row">
            <label>Type:
              <select id="e_type"><option value="">(all)</option><option>CONTRACT</option><option>PROOF_OF_DELIVERY</option><option>PRE_ACTION_NOTICE</option><option>OTHER</option></select>
            </label>
            <label>Limit:<input id="e_limit" value="100" /></label>
            <label>Offset:<input id="e_offset" value="0" /></label>
            <button onclick="viewEvidence()">Refresh Evidence</button>
          </div>`;
        await viewEvidence();
        return;
      }
      if (tabName === "ledger") {
        panel.innerHTML = `
          <div class="row">
            <label>Event Type:<input id="l_type" value="" /></label>
            <label>Limit:<input id="l_limit" value="100" /></label>
            <label>Offset:<input id="l_offset" value="0" /></label>
            <button onclick="viewLedger()">Refresh Ledger</button>
            <button onclick="viewDebtorLedger()">Debtor Ledger A</button>
            <button onclick="viewClientFeeLedger()">Client Fee Ledger B</button>
          </div>`;
        await viewLedger();
        return;
      }
      if (tabName === "hygiene") {
        panel.innerHTML = `
          <div class="row">
            <label>Creditor Name:<input id="h_creditor_name" value="First Cairn Digital Ltd" /></label>
            <label>Creditor CH #:<input id="h_creditor_ch" value="SC123456" placeholder="SC123456 or 12345678" /></label>
            <label>Creditor VAT #:<input id="h_creditor_vat" value="GB123456789" placeholder="GB123456789" /></label>
          </div>
          <div class="row">
            <label>Creditor Address:<input id="h_creditor_addr" value="1 Example Street, Glasgow" /></label>
            <label>Debtor Name:<input id="h_debtor_name" value="Example Buyer Ltd" /></label>
            <label>Debtor CH #:<input id="h_debtor_ch" value="NI654321" placeholder="NI654321 or 87654321" /></label>
            <label>Debtor VAT #:<input id="h_debtor_vat" value="GB987654321" placeholder="GB987654321" /></label>
            <label>Debtor Address:<input id="h_debtor_addr" value="2 Sample Road, Belfast" /></label>
          </div>
          <div class="row">
            <label>PO Required:<select id="h_po_required"><option value="false">false</option><option value="true">true</option></select></label>
            <label>PO Ref:<input id="h_po_ref" value="" /></label>
            <label>Terms Days:<input id="h_terms" value="30" /></label>
          </div>
          <div class="row">
            <label>Interest Clause:<select id="h_interest"><option value="true">true</option><option value="false">false</option></select></label>
            <label>Recovery Clause:<select id="h_recovery"><option value="true">true</option><option value="false">false</option></select></label>
            <label>Proof Required:<select id="h_pod"><option value="true">true</option><option value="false">false</option></select></label>
          </div>
          <div class="row">
            <label>Suggested Clause:<input id="h_clause" value="" /></label>
            <label>Notes:<input id="h_notes" value="" /></label>
          </div>
          <div class="row">
            <button onclick="recordWorkspaceHygiene()">Record Hygiene</button>
            <button onclick="viewWorkspaceHygiene()">List Hygiene</button>
          </div>`;
        await viewWorkspaceHygiene();
        return;
      }
      panel.innerHTML = `
        <div class="row"><label>Today:<input id="a_today" value="2026-02-10" /></label>
        <label>State:
          <select id="a_state"><option>ISSUED</option><option>FRIENDLY_REMINDER</option><option>OVERDUE_CHASER</option><option>FORMAL_NOTICE</option><option>PRE_ACTION_PROTOCOL</option></select>
        </label>
        <button onclick="runEscalation()">Run Escalation</button></div>
        <div class="row"><button onclick="runLatePayment()">Late Payment Calc</button>
        <button onclick="runManifest()">Manifest JSON</button>
        <button onclick="verifyManifest()">Verify Manifest</button></div>`;
    }

    async function viewSummary() { await request(`/invoices/${invoiceId}`, "GET"); }
    async function viewEvidence() {
      const params = new URLSearchParams();
      const t = document.getElementById("e_type");
      if (t && t.value) params.set("artifact_type", t.value);
      params.set("limit", (document.getElementById("e_limit")?.value || "100"));
      params.set("offset", (document.getElementById("e_offset")?.value || "0"));
      await request(`/invoices/${invoiceId}/evidence-artifacts?${params.toString()}`, "GET");
    }
    async function viewLedger() {
      const params = new URLSearchParams();
      const t = document.getElementById("l_type");
      if (t && t.value) params.set("event_type", t.value);
      params.set("limit", (document.getElementById("l_limit")?.value || "100"));
      params.set("offset", (document.getElementById("l_offset")?.value || "0"));
      await request(`/invoices/${invoiceId}/ledger-events?${params.toString()}`, "GET");
    }
    async function viewDebtorLedger() { await request(`/invoices/${invoiceId}/debtor-ledger`, "GET"); }
    async function viewClientFeeLedger() { await request(`/invoices/${invoiceId}/client-fee-ledger`, "GET"); }
    async function recordWorkspaceHygiene() {
      await request(`/invoices/${invoiceId}/pre-overdue-hygiene`, "POST", {
        creditor_legal_entity_name: document.getElementById("h_creditor_name").value,
        creditor_companies_house_number: document.getElementById("h_creditor_ch").value,
        creditor_vat_number: document.getElementById("h_creditor_vat").value,
        creditor_trading_address: document.getElementById("h_creditor_addr").value,
        debtor_legal_entity_name: document.getElementById("h_debtor_name").value,
        debtor_companies_house_number: document.getElementById("h_debtor_ch").value,
        debtor_vat_number: document.getElementById("h_debtor_vat").value,
        debtor_trading_address: document.getElementById("h_debtor_addr").value,
        po_required: document.getElementById("h_po_required").value === "true",
        po_reference: document.getElementById("h_po_ref").value || null,
        payment_terms_days: Number(document.getElementById("h_terms").value || "0"),
        contractual_interest_clause_present: document.getElementById("h_interest").value === "true",
        contractual_recovery_clause_present: document.getElementById("h_recovery").value === "true",
        proof_of_delivery_required: document.getElementById("h_pod").value === "true",
        suggested_clause_text: document.getElementById("h_clause").value || null,
        notes: document.getElementById("h_notes").value || ""
      });
    }
    async function viewWorkspaceHygiene() {
      await request(`/invoices/${invoiceId}/pre-overdue-hygiene`, "GET");
    }
    async function runEscalation() {
      await request(`/invoices/${invoiceId}/escalate`, "POST", {
        today: document.getElementById("a_today").value,
        current_state: document.getElementById("a_state").value
      });
    }
    async function runLatePayment() {
      await request(`/invoices/${invoiceId}/late-payment-calculations`, "POST", {
        as_of_date: "2026-03-15", is_commercial_transaction: true, base_rate_override: "0.05"
      });
    }
    async function runManifest() {
      await request(`/invoices/${invoiceId}/ledger-manifests`, "POST", {
        output_filename: "manifest.json", output_format: "json"
      });
    }
    async function verifyManifest() {
      await request(`/invoices/${invoiceId}/ledger-manifests/verify`, "POST", {
        output_filename: "manifest.json"
      });
    }

    loadTab("summary");
  </script>
</body>
</html>
"""
    return template.replace("__INVOICE_ID__", invoice_id)
