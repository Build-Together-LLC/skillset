# House content — reusable blocks

Copy these into a generator and adjust. Figures were current as of **August 2026** — re-check hosting
and AMC pricing before sending, and scale AMC to the size of the implementation.

---

## App stack table

Include only apps actually installed on the target bench. A typical bench carries:
`frappe`, `erpnext`, `hrms`, `crm`, `india_compliance`, `insights`, `frappe_whatsapp`, `payments`,
`pos_next`, `email_delivery_service`, `lms`, `education`, `wiki`. Larger benches may also carry
`raven`, `print_designer`, `excel_view`, `helpdesk`, `gameplan`, `cn_indian_payroll`,
`cn_leave_shift_managment`, `cn_todo_manager`, `visitor_management`, `telephony`, `sms_integration`,
`india_banking`, `posawesome`, `recruitment` — useful as "proven assets we reuse".

```python
d.table(["App / Module", "What It Does for You", "Licence"], [
    ["Frappe Framework", "DocTypes, workflows, roles, permissions, notifications, REST APIs, audit trail", "FREE"],
    ["ERPNext — Selling", "Customers, SO, Delivery Note, Sales Invoice, price lists, pricing rules, credit limits", "FREE"],
    ["ERPNext — Buying", "Suppliers, Purchase Order, Purchase Receipt (GRN), Purchase Invoice", "FREE"],
    ["ERPNext — Stock", "Warehouses, stock ledger, Pick List, reorder levels, stock reconciliation", "FREE"],
    ["ERPNext — Projects", "Projects, Tasks, timesheets, project-wise activity tracking", "FREE"],
    ["Frappe CRM", "Organizations, Leads, Deals, pipelines, call and email logs, task assignment", "FREE"],
    ["Frappe HR (HRMS)", "Employee lifecycle, attendance, shifts, leave, expense claims, payroll, self-service", "FREE"],
    ["India Compliance", "GSTIN validation, GST fields, e-invoice / e-way bill readiness", "FREE"],
    ["Insights", "BI dashboards — sales, stock, purchase, CRM pipeline, HR metrics", "FREE"],
    ["Frappe WhatsApp", "WhatsApp Cloud API templates — invoices, delivery notes, reminders", "FREE"],
    ["Print Designer", "Print formats for Sales Order, Delivery Note, Pick List, invoices", "FREE"],
    ["Custom <X> App (by us)", "<the 25% that is genuinely theirs>", "Included"],
], caption="Solution Building Blocks", widths=[1.5, 4.2, 0.8])
```

Always state: **Total software licence cost: ₹ 0, for unlimited users.**

---

## Why this wins

```python
d.table(["Factor", "ERPNext + Frappe (This Proposal)", "Typical Closed <X>"], [
    ["Software licence", "FREE — open source, unlimited users", "Per-user / per-module, yearly"],
    ["Customisation", "Low-code DocTypes and workflows — days", "Change request and quotation"],
    ["Ownership", "You own all code and data", "Vendor-owned, locked"],
    ["India statutory", "India Compliance + payroll statutory built in", "Add-on module, extra cost"],
    ["Reporting", "Report Builder, Query Reports and Insights included", "Fixed report set"],
], caption="Why This Approach Wins", widths=[1.4, 2.9, 2.2])
```

---

## Hosting

```python
d.table(["vCPUs", "Memory", "Disk", "Monthly (INR)", "Annual (INR)"], [
    ["2 vCPUs", "8 GB", "50 GB", "₹ 12,000 / mo", "₹ 1,44,000 / yr"],
    ["4 vCPUs ⭐ recommended", "16 GB", "100 GB", "₹ 24,000 / mo", "₹ 2,88,000 / yr"],
    ["4 vCPUs", "32 GB", "100 GB", "₹ 32,000 / mo", "₹ 3,84,000 / yr"],
], caption="Indicative Frappe Cloud Plans (paid to Frappe Cloud directly by you)",
   widths=[1.7, 0.9, 0.9, 1.5, 1.5])
```

Sizing: 2 vCPU / 8 GB for a single site or small store; 4 vCPU / 16 GB once CRM, HR and Insights run
together; 4 vCPU / 32 GB for heavy logging (GPS, high document volume). Always say hosting is paid by
the client directly, is **not** bundled into implementation, and carries no licence fee on top.

---

## AMC tiers

Scale to the implementation: Basic ≈ 13% of one-time, Standard ≈ 22%, Premium ≈ 32%.

```python
d.table(["Service", "Basic", "Standard (Recommended)", "Premium"], [
    ["Bug fixes (delivered customisations)", "Yes", "Yes", "Yes"],
    ["ERPNext / app version updates", "After testing", "After testing", "Priority"],
    ["Support channel", "Email, 24-hr", "Email + phone, 8-hr", "Priority, 4-hr"],
    ["Business-stoppage escalation", "Next business day", "Same day", "Fastest"],
    ["Minor enhancements", "Not included", "Up to 8 hrs / month", "Up to 20 hrs / month"],
    ["Statutory / compliance updates", "Quoted", "Included", "Included (priority)"],
    ["New report requests", "Quoted", "Up to 2 / quarter", "Up to 2 / month"],
    ["Health check & review", "Annual", "Half-yearly", "Quarterly"],
    ["Indicative annual cost (INR)", "~ X", "~ Y", "~ Z"],
], caption="Annual Maintenance Tiers", widths=[2.0, 1.4, 1.7, 1.4])
```

Precede with: 30-day stabilisation with priority support included after go-live; AMC is optional
because the client owns the source code.

---

## Payment terms

Milestone-linked, summing to 100%. Two shapes that work:

- **Two-track:** 35% kickoff · 25% Track A go-live · 30% Track B go-live · 10% after stabilisation
- **Sequential:** 40% kickoff · 25% mid-phase go-live · 25% final go-live · 10% after stabilisation

Close with: *"All prices are exclusive of GST, charged extra as applicable. Third-party costs —
hosting, WhatsApp Cloud API charges, telephony, map or Google Workspace subscriptions — are billed at
actuals to you."*

---

## Out of scope (standard set — trim to what applies)

- Migration or integration explicitly deferred to a future module (name it, and point at the price)
- Statutory filing as a service — GST returns, e-invoicing, PF / ESI portal submissions, TDS returns.
  The system produces the data; filing is by their team or CA
- Supply of hardware — servers, scanners, printers, biometric devices, phones, POS terminals
- Third-party subscriptions billed at actuals — hosting, WhatsApp Cloud API, Google Workspace, SMS,
  telephony, GPS / SIM data, map or geocoding APIs
- Historical data migration beyond the agreed scope and period
- Anything the client explicitly asked to be excluded — say *"deliberately excluded at your
  instruction"*, so it reads as a decision rather than a gap
- Internet, LAN / Wi-Fi or electrical infrastructure at their premises
- Travel, boarding and lodging for on-site visits — at actuals, if required

---

## Acceptance & sign-off

```python
d.body(
    "By signing below, the authorised representatives confirm their agreement to proceed as "
    "described. Detailed scope, exact timelines and final commercials will be confirmed in a "
    "Statement of Work after a short discovery with your team."
)
d.table(["Role", "Name", "Signature", "Date"], [
    ["Prepared By (Implementer)", "Build Together", "N/A", "N/A"],
    ["Accepted By (Client)", "<Client legal name>", "N/A", "N/A"],
    ["Approved By (Client Management)", "N/A", "N/A", "N/A"],
], caption="Acceptance", widths=[2.2, 1.8, 1.4, 1.1])
```

Close with a two-sentence thank-you that names the client's own words back to them, then:

```python
d.body("Build Together   |   mehek@buildtogether.co.in   |   +91 98306 75002   |   www.buildtogether.co.in",
       align="center", bold=True)
```

---

## Phrases that carry weight

- *"Total software licence cost: ₹ 0 (Zero) — for unlimited users."*
- *"You own the source code and your data."*
- *"We configure the 75% that already exists and build only the 25% that is genuinely yours — lower
  cost, lower risk."*
- *"Not everything needs to be automated on day one."* — when the client has asked you to leave a
  system alone
- *"<Decision> is deliberate, not a gap."* — for anything a competitor would quote as a feature
