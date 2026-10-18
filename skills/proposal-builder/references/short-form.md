# SHORT form — consolidated proposal (~20–25 pages)

8 numbered H1 sections plus 2 annexures. This is the default format: an owner will read it end to end,
and it is the right document to negotiate from. Reference implementation: the AMK Bearings proposal.

Module detail lives in **bullets, not tables** — that single choice is worth ~15 pages.

---

## Structure

| # | Section (H1) | Contains | Budget |
|---|---|---|---|
| — | Cover | 4 centred paragraphs + Document Control table (incl. a one-line Contents row) | 1 p |
| 1 | Executive Summary | 2 paragraphs + "Proposal at a Glance" table | 1 p |
| 2 | Understanding Your Business | Operation Snapshot table; H3 differentiator table (if two-mode business); H3 current challenges (6 bullets) | 2 p |
| 3 | Platform & Solution Stack | Framing paragraph; app stack table; H3 "Why This Wins"; H3 architecture decision | 2 p |
| 4 | Scope — Module by Module | One H3 per module, 5–7 one-line bullets each; keep tables only where genuinely tabular (e.g. the reporting pack) | 3–4 p |
| 5 | *Client-specific pivot* | The one thing this deal turns on — e.g. Tally coexistence, offline POS, compliance regime. Flow table + deliberate-decision banner | 1 p |
| 6 | Implementation, Timeline & Effort | Methodology paragraph; combined phase + timeline + milestone table; H3 effort distribution (two-column layout) | 2 p |
| 7 | Investment & Hosting | H3 per module breakdown (Scope column references Section 4.x, not restated); phasing; hosting; optional future modules; recurring + payment terms | 2–3 p |
| 8 | Deliverables, Support & Terms | H3 deliverables (bullets); AMC tiers table; why-our-approach paragraph; out-of-scope bullets; acceptance table + closing paragraph + contact line | 2 p |
| A | Requirement Coverage Matrix | Full length — one row per requirement. **Never abbreviate this to save space** | 2–3 p |
| B | Technical Notes & Open Questions | H3 the critical flow as `d.code(...)`; H3 roles + approval tables; H3 open questions | 2 p |

---

## Rules that keep it short

- **No Table of Contents H1.** The Document Control table carries a one-line Contents row instead:
  `"1 Summary · 2 Your Business · 3 Platform · 4 Scope · …"` — saves a page and a numbering reset.
- **Section 4 is bullets.** Format each as `"<Capability>: <what it does>"`, one or two lines. Aim for
  ≤ 92 characters to stay on one line.
- **Section 7 does not restate scope.** The Scope column reads `Section 4.4`, not a paragraph.
- **Deliverables are bullets, not a numbered table.** They restate Section 4 by nature; keep them
  one line each and do not expand.
- **One capability, one home.** If it is in the module bullets and in the coverage matrix, it does
  not also need a summary table.

## What to cut if it is still too long

In order — stop as soon as you are under budget, and tell the user what went:

1. Module bullets down to 3–4 per module (the coverage matrix still carries the rest)
2. Merge sections 5 and 4 (pivot becomes `4.9`) — removes an H1
3. Merge Annexure B into Annexure A as sub-headings — removes an H1
4. Drop the "Why This Wins" comparison table
5. Drop Annexure A — **last resort only**, and say explicitly that the point-by-point audit trail
   against their requirement discussion is what is being given up
