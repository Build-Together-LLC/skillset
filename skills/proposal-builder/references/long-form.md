# LONG form — detailed proposal (~50–65 pages)

~25–30 numbered H1 sections plus annexures, one H1 per module. Use when a technical buyer or a
committee will review it, or when every design decision must be on record. Reference
implementations: Liquor Vault Goa POS, e-Yantram E-Waste ERP, AMK Bearings (v1).

---

## Structure

| # | Section (H1) | Contains |
|---|---|---|
| — | Cover | 4 centred paragraphs + Document Control table |
| — | Table of Contents | Plain `d.body()` lines, left-aligned. **Reset `d._section_no = 0` immediately after this H1** |
| 1 | Executive Summary | 3–4 paragraphs + H3 "What This Proposal Covers" (10–14 bullets) |
| 2 | Understanding Your Business | H3 operation snapshot table; H3 differentiator table; H3 current challenges; H3 what you want |
| 3 | Why ERPNext, Frappe & <CRM/HR/…> | H3 requirement-to-platform mapping table; H3 why-this-wins table; H3 governing principle |
| 4 | Proposed Solution Overview | App stack table with licence column |
| 5 | *Architecture / operating model* | The structural decision — two buckets, offline-first, multi-company — with a separation map table |
| 6…N | **One H1 per module** | See module template below |
| N+1 | *Client-specific pivot* | Tally coexistence, compliance regime, offline strategy — whatever the deal turns on |
| N+2 | Proven Assets We Reuse | Table: asset / where it runs today / what it gives this project. Justifies the price |
| N+3 | Implementation Approach & Phases | H3 methodology bullets; H3 phases as `title (bold) / Objective: / Deliverable:` blocks |
| N+4 | Timeline & Milestones | Phase timeline table + calendar paragraph + assumption |
| N+5 | Hosting | Frappe Cloud plan table + recommendation |
| N+6 | Investment Summary | H3 module breakdown; H3 phasing; H3 optional future modules; H3 recurring; H3 payment terms |
| N+7 | Deliverables | Numbered table, one row per deliverable |
| N+8 | Post Go-Live Support | AMC tier comparison table |
| N+9 | Our Relevant Experience | Positioning paragraph + H3 why-our-approach bullets |
| N+10 | Out of Scope & Exclusions | Bullets |
| N+11 | Acceptance & Sign-Off | Acceptance table + closing paragraph + contact line |
| A | Requirement Coverage Matrix | `Area | Your Requirement | How It Is Delivered | Type` |
| B | Architecture notes | Why the structural decision was made, and the separation mechanisms |
| C | Critical flow | The one process most likely to be misbuilt, as `d.code(...)` + exception table |
| D | Roles, Approvals & Permissions | Role map table + approval points table |
| — | Open Questions for Discovery | Bullets + a line saying none of them block the proposal |

---

## Module template (one H1 each)

```python
d.banner("9. MODULE 4 — SALES: AUTOMOBILE BUCKET", "The channel, the price and the controls")
d.h1("9. Module 4 — Sales: Automobile Bucket")

d.h3("9.1 <Capability area>")
d.body("Your Requirement: <quote or close paraphrase of what they asked for>.")
for b in [...]:            # 4-6 bullets: how we solve it
    d.bullet(b)
d.body("Result: <what changes for them>.")     # optional, for the ones that matter

# ... more H3 capability areas ...

d.h3("9.N Module Summary")
d.table(["Feature", "What It Does", "Your Benefit"], [...], caption="<Module> Capability Summary")
```

The `Feature | What It Does | Your Benefit` closing table is the LONG-form signature — it lets a
skim-reader take the module in one glance. It is also the first thing to delete when converting to
SHORT.

---

## Converting LONG → SHORT

1. Collapse every module H1 into one H3 under a single `Scope — Module by Module` H1.
2. Turn each module's H3 sub-sections into 5–7 bullets; drop the `Your Requirement:` quotes (the
   coverage matrix carries them) and drop the capability summary tables.
3. Merge Hosting into Investment; merge Deliverables, Support, Experience, Exclusions and Sign-Off
   into one `Deliverables, Support & Terms` H1.
4. Merge annexures B/C/D into one `Technical Notes & Open Questions`.
5. Replace the Table of Contents H1 with a Contents row in the Document Control table.
6. Replace the investment table's Scope column with `Section 4.x` cross-references.

Expect roughly a 60% reduction. Re-run the page estimator after each step rather than at the end —
it tells you which cut actually paid.
