---
name: vipl-reorder
description: "VIPL's reorder / purchase-ordering engine — decides what to buy, how much, and when, brand by brand. Runs the refresh pipeline, applies the ordering rules Viren has approved, and publishes the reorder dashboard. Use for any question about what to order, reorder quantities, MOQ, stock cover, pending POs, overstock, stock-outs, the order calendar, or the reorder dashboard for VIDIRA / VIPL."
---

# VIPL — Reorder engine

Decides **what to buy, how much, and when** for **VIDIRA INNOVATIONS PVT LTD (VIPL)**, a
two-wheeler spare-parts distributor in Burdwan with a second branch in Siliguri, on **ERPNext
V16** (`vidira.m.frappe.cloud`). Output is a reviewable order list per brand, not an automatic
purchase order — **Viren or Dinesh always presses the button.**

Viren is non-technical. Plain answers, real numbers, caveats stated first. **When he says a
number looks wrong, re-measure before defending it.** He has been right every time.
All dates and times are **IST**; the shell reports UTC.

---

## ⚠ NEVER STOP COUNTING GOODS AS INCOMING WITHOUT ASKING VIREN FIRST

**Viren, 2026-09-14: "before stopping counting as incoming always confirm with me first … dont
stop varroc's goods as not incoming."**

Dropping something from incoming is the most expensive silent act the tool can perform: it makes
the item look short, and the next order buys goods that are already on their way. Age is never
evidence that goods are not coming.

**The split that matters:**

| Kind of retirement | What it means | Allowed without asking? |
|---|---|---|
| Receipts in the purchase register (`ORDER_LOG_RETIRE_ON_RECEIPT`) | the goods LANDED — netted off code by code | **Yes** — evidence |
| Every line now sits on an ERP PO raised on/after the log | now counted from ERP pending instead | **Yes** — the goods moved counter, they were not lost |
| Log is older than the brand's cycle + grace | a GUESS that it landed or will never come | **NO — ask first** |

The age rule used to drop the log outright. On 14-Sep five Varroc logs (30-Jul → 29-Aug,
21,892 pcs) aged out **mid-session** and pushed the Varroc order from ₹0.45 L to ₹3.25 L on goods
Varroc may still owe. `engine.py` now **keeps an over-age log counting** and prints:

```
*** ORDER LOGS PAST THEIR CYCLE — STILL COUNTED AS INCOMING, CONFIRM WITH VIREN ***
```

with lines, pieces and age per file. **Relay that list to Viren every refresh.** He retires a file
by deleting it from `09 ORDER LOG/`; nothing else retires it on age. Never delete one yourself, and
never quietly re-enable the age cut-off.

The exposure runs the other way too, and say so plainly: if those goods actually landed long ago,
the tool is now over-counting incoming and **under**-ordering. That is why the confirmation list
exists — it is a question for Viren, not a number to defend. The supplier's own statement of what
they still owe is the tiebreaker (see *Cancelling POs*).

The same rule governs anything else that removes incoming: `EXCLUDE_POS`, cancelling a PO,
retiring a `SUPPLIER CONFIRMED PENDING.csv` row. Ask, then act.

---

## ⚠ WHEN VIREN UPLOADS A PLACED-ORDER FILE — READ THIS FIRST

This is the single most repeated mistake. It has produced a wrong "you changed N lines" claim
**three times in one day** (FIEM, Varroc, ANL, 2026-08-26 to 08-31). Each time Viren had changed
nothing of the sort, and each time the fault was comparing against the wrong reference.

**The rule: compare his file against WHAT THE DASHBOARD SHOWED HIM, never against a CSV you
generated, and never against the live engine state.**

Procedure, in order:

1. **Read the date stamp in the filename.** Exports are named
   `<BRAND>_order_<DDMonYYYY>.xlsx` where the date is the **data as-on date**, not the day he
   ordered. `ANL_order_29Aug2026.xlsx` came from the build whose data ran to 29-Aug.
2. **If that date is not today's `asof`, say so and do not compare on quantities** until you
   have reconstructed the state at that date. Quantities move on every refresh; a file one
   refresh old will differ everywhere and none of it is his doing.
3. **The reference is the dashboard's order view for that brand — every line with
   `oB > 0` / `oS > 0` — not the order CSV you wrote.** Those differ: a CSV you build for a
   specific purpose (a budget plan, a month-end top-up) contains only the lines you chose,
   while the dashboard also shows the engine's own suggestions and any `MANUAL QTY EDITS`.
   Lines carrying no `me` flag are the tool's own; lines flagged `edited X→Y` are forced ones.
4. Only then report differences, and phrase them as *quantity changes*, not additions, unless
   the code genuinely appears nowhere in the dashboard view.
5. If you cannot reconstruct the reference, **ask which file he worked from** rather than
   guessing. One question costs less than a false accusation.

The same discipline applies to any "why has this changed since yesterday" question: establish
which build he is looking at before explaining a delta. The dashboard header shows
*Data as on <date>*; the splice rewrites it every run from `cache/asof.txt`.

**Logging a placed order** — write `09 ORDER LOG/ORDER PLACED <BRAND> <DDMonYYYY>.csv` with columns
`brand,branch,code,qty`, then re-run `engine.py` and `splice_dashboard.py`. Check the codes exist in
the item master first; a code the master doesn't know adds nothing and fails silently. If the order
includes a code you forced through `MANUAL QTY EDITS.csv`, **remove that row in the same turn** — it
is placed now, and leaving it re-forces the quantity on every future refresh.

---

## The pipeline — order matters, and a half-run is worse than yesterday's

```
bash "<CoWork>/Reorder Tools/scripts/run_refresh.sh"
```

Fail-fast (`set -euo pipefail`). A partial refresh looks current and isn't.

| # | Script | Does |
|---|---|---|
| 1 | `load_sales.py i j` | monthly Sale Registers → `sales_YYYY-MM.pkl` (chunked) |
| 2 | `load_purch.py i j` | monthly Purchase Registers → `purch_YYYY-MM.pkl` (same chunking) |
| 3 | `load_stock.py` | Stock Balance → `stock.pkl` — **must run every refresh**; applies `STOCK ADJUSTMENTS.csv` |
| 4 | `load_varroc_intransit.py` | Varroc control files → in-transit |
| 5 | `build_pending.py` | open POs, nets off unlinked receipts, applies `EXCLUDE_POS` and `SUPPLIER CONFIRMED PENDING.csv` |
| 6 | `build_caches.py` | rebuilds 7 pickles the engine needs but nothing else writes. **Without this the engine cold-starts broken.** |
| 7 | `engine.py` | the decision layer |
| 8 | `splice_dashboard.py` | injects DATA into the dashboard HTML shell and rewrites the header date |

**Run the scripts from their real location in CoWork. Do not run them from a copied/sed-ed
mirror** — every script derives its root from `__file__`, so a copy sitting in `outputs/`
resolves the CoWork path to `/sessions` and dies, or worse reads a stale mirror. A drifted
mirror once hid two order logs and overstated the order by ₹25 L (2026-08-29).

All scripts derive their root from `__file__` — **never hardcode `/sessions/<name>/`**.
Cache lives in `outputs/cache/`. CoWork root is Google Drive `VIPL CoWork` (needs "Available
offline"), and it is the **single home** for the tool: engine, shell and outputs all live there,
with no second copy in a local project folder. Every file written must have a **Windows-safe
name** — the team is on Windows.

Run stages in the **foreground**, one call each (`run_refresh.sh` in a single call exceeds the
shell timeout). A backgrounded run is killed the moment the call returns and the log just stops.
Before editing `engine.py`, copy it to `engine.py.bak-<DDMon>` and `ast.parse` the result.

---

## How the quantity is decided

```
demand    = max(12-month average, last 3 complete months, live run-rate)
target    = demand × (lead + review)/30 × seasonality + safety
safety    = Z(class) × std × sqrt((lead + review)/30)
order     = target − stock − pending,  rounded up to MOQ
```

- **ABC by value contribution within each brand**: A ≤80%, B ≤95%, C ≤99%, D the rest.
- **`Z = {A: 2.33, B: 1.04, C: 0.67, D: 0.0}`** — service level by class.
- **`REVIEW = 7`** days default; `REVIEW_BY_BRAND_PREFIX` overrides (VIDIRA 30).
- **`LEAD`** per brand, measured not assumed (Aerostar/Shree Amba 16, default `DEF_LEAD = 15`).
- **Live run-rate** (`RUNRATE_CLASSES` = A,B,C,D; `RUNRATE_CAP = 2.0`): a 12-month average
  lagged rising items and caused the AS-391C stock-out. Current month counts only after
  `CURMONTH_MIN_DAYS = 12`.
- **Seasonality** indexes the month being ordered *for*, not the current one.
- **New items** need `NEW_ITEM_MIN_MONTHS = 2.0` of trading before their rate is trusted;
  new brands get `NEW_BRAND_MONTHS = 6`. Watch for double-boosting a new item in a new brand.

**Whenever you add or change a demand/order adjustment, grep every LATER block that writes the
same column and confirm it is not compounding.** This has bitten four times: VGA45AC (new-item
average × run-rate), the Spark Minda lock kits (Siliguri MOQ rule placed before the new-brand
trigger), AS-551C (`SILIGURI_RAMP` then boosted again by the run-rate), and the WP-twin excess
fix (mirrored only half of `max(up, am × keep_months)`).

**A brand that re-orders a code Viren just bought is usually not a bug.** Check cover first:
`(stock + pending) ÷ demand`. On 14-Sep Varroc re-ordered 22 codes he had ordered that morning, and
every one sat under 1.1 months of cover with his order already counted. Show him the cover column
before calling anything a double-count.

---

## The rules Viren has approved — do not quietly change these

| Flag | Rule | Why |
|---|---|---|
| `QUIET_PERIOD = True`, `QUIET_MULT = 1.0` | don't re-order a code whose open PO is younger than its measured lead time | stops double orders |
| **the safety valve on it** | hold applies **only when stock + pending ≥ lead + review** | without it fast movers starve |
| `CLASS_REVIEW = {"C": 30, "D": 30}` | slow items qualify monthly, not weekly | ~2× pieces per line, 25% less handling |
| `CD_LAST_WEEK_ONLY = True` | C/D held unless ≤6 days to month end | lands off the warehouse's peak |
| `COVER_CAP = 6` | MOQ cap — skip if one pack exceeds 6 months of demand | pack size forced 43% of overstock |
| `MOQ_SKIP_BELOW = 0.5` | wait rather than buy under half a box | |
| `SILIGURI_MAX_COVER = 12`, `SG_BUFFER = 1.35`, `SILIGURI_RAMP = True` | suppress >12-month cover → transfer instead. **Must run LAST** | fractional need × MOQ gave 60-month cover |
| `SIL_MIN_MONTHS = 2` | **bold on transfers, careful on buying** — an item with <2 months of Siliguri history uses the full live-month rate for `xBS` transfers but a halved rate (`sdm_buy`) for direct purchase | Siliguri opened Jan-2026 and is still ramping; a transfer from Burdwan surplus is free and reversible, a purchase is not |
| `AEROSTAR_PORTAL_ADDS_PENDING = False` | Aerostar pending comes from **our own POs** only | the portal file double-counted |
| `NO_ORDER` set | never auto-order these (incl. `PRZ9HC`, superseded by `CPRZ7HC`) | |
| `SCHEME_TOPUP = {}` | scheme brands are opt-in per scheme, never standing | Rockman and Varroc Mobil are scheme lines |
| `BRAND_MOQ_FORCE = {"LUMAX": 1, "AVON": 10}` | supplier-confirmed pack overrides | |
| `DEAD_NOSALE_DAYS = 365`, `DEAD_MIN_AGE = 120` | dead = not sold in 12 months, by days-since-last-sale | not `an`/`so` |
| `ORDER_LOG_RETIRE_ON_RECEIPT = {"SENIOR"}` | a placed order counts as pending until **received** | Senior bills under 3 firms and raises no ERP PO |
| `ORDER_LOG_GRACE_DAYS = 7` | sets only **when a log is LISTED for confirmation** — it no longer retires anything | age is a guess, not evidence (Viren 2026-09-14) |
| **per-line log retirement** | a log line leaves the moment ITS code appears on a PO raised on/after the order — never all-or-nothing | the old 60% threshold double-counted below it and dropped genuine incoming above it |
| `NEW_ITEM_DAYS = 90` | "new to the range" = first **purchase** AND first **sale** both within 90 days | first-purchase alone flags old lines simply not restocked for months (WIGSWSSPL69DZ); last-purchase flags anything recently restocked (5,164 false positives) |
| `ADD_COVER = 2.0` (dashboard) | an item only appears in the *Add items* views if the branch holds under 2 months, or holds none at all | a line with 58 months of cover was showing as an "add" candidate |

**VEGA**: helmets are fashion SKUs — MOQ forced to 1; the ALL-IN-ONE catalogue is **partial**
(missing CLARK/SPIKE), so never auto-suppress on its absence. New model qty = models × colours,
1 month cover, 5-piece trial.

---

## Cancelling POs — the policy changed on 2026-08-29

**Only cancel a PO after the supplier confirms they will not supply it.** Do not offer to cancel
on age alone. Cancelling in the tool does not cancel with the supplier: it creates a second claim
on the same goods, and if the old PO later ships it arrives on top. Spaco was cancelled and
re-ordered four times, NGK six POs, NOK three — and the Aerostar over-delivery (444 codes,
₹28.56 L ordered twice) came from the same family of mistake.

When a supplier sends their own statement of what they still owe, that **beats** our ERP balance:
put it in `05 STOCK & OPEN ORDERS/SUPPLIER CONFIRMED PENDING.csv` (code, branch, qty). Neither
that file nor `STOCK ADJUSTMENTS.csv` expires by itself — **delete the row once the goods land or
the recount is done**, or the tool believes it forever.

A **fill-rate discount on pending was considered and rejected**: suppliers fill 30–70% of a PO but
the balance usually arrives late rather than never, so discounting pending makes the tool order
more and worsens the pile-up. The fixes that work are the duplicate-PO guard, per-line log
retirement, and dated export filenames.

---

## Traps that have each produced a wrong order

1. **Stale as-of date.** `ASOF_TS` was once hardcoded 46 days behind — dead stock understated
   ₹2.6 L. Derive from `DATA_MAX`, never hardcode.
2. **Date parsing.** `dayfirst=True` on ISO text dates wiped 588 Aug-2026 purchase rows.
   Loaders are format-aware with a hard guard — keep it.
3. **Purchase register multi-month exports.** The loader clamps rows to the month in the filename.
4. **Sale Register grand-total row.** Drop rows with no `Item Code` and `Item Code == "total"`.
5. **Truncated PO export.** A short export inflated the order by ₹36 L. Check date range and PO
   count before publishing, and **filter out `Closed` POs** — PO Analysis shows phantom pending
   on them (₹1.4 crore company-wide; Varroc alone 23,000 pcs).
6. **Unlinked receipts.** 77.7% of receipts are booked with no PO link → phantom pending.
7. **Duplicate order-log files.** The engine collapses identical logs by content hash.
8. **Stock must be rebuilt every refresh.**
9. **ERPNext Custom Reports ignore API filters.** Call the base report and assert the window.
10. **Varroc pending** comes from the control files, not the ERP — and **never add an order log
    on top of the Varroc fresh-pending file**; the file already includes logged orders. Take the
    higher of the two, never the sum (this double-counted ₹2.18 L). The de-dup prints
    `VARROC de-dup: N codes are in BOTH …` — that line is the guard working, not a fault.
11. **Avon incoming** = dispatch invoices, not the stale phantom PO.
12. **WP twins** (`-WP` codes) are the same physical part as their base. Judge their excess on the
    **pooled** position using the same `max(up, am × keep_months)` formula, or 78 items show
    ₹49 k of false excess.
13. **Render cap.** `currentRows()` caps at 600 rows (`cap:` per view). Without it the *Add items*
    views matched 19,508 rows and froze the browser on every keystroke.
14. **Parsing supplier invoice PDFs.** Anchor the quantity on the token *before* the UOM *and*
    the price after it — `(\d+)\s+(NOS|SET|PCS)\s+([\d,]+\.\d{2})`. A description containing a
    number ("SIDE COWL PHOENIX 125 SET OF 4") otherwise reads as qty 125.
15. **The company order total moves between runs within one session.** Logging an order changes
    which other logs retire and can drop a brand under the 40-line narrow-range threshold,
    releasing its deferred C/D lines. Explain a delta by naming what retired or released — never
    report it as noise, and never as the user's doing.

Sanity guards already in `engine.py`: `MIN_MASTER_ROWS = 50000`, CoWork-path candidates, the
duplicate-PO guard, and the fail-fast in `run_refresh.sh`. Leave them in.

---

## Things Viren has decided that look like improvements and are not

- **Never ask suppliers to consolidate dispatches.** Being first in the allocation queue beats a
  tidy delivery schedule. Daily arrivals are the price of supply.
- **Don't promise capital release from ordering changes.** Overstock is money already spent; it
  returns by selling, not by ordering less.
- **Don't regenerate the dashboard HTML shell** — splice DATA only. The schemes panel, branch
  selector and view definitions live in the shell.
- **Raising `A_CAP_MONTHS` 1.5 → 2.0 was rejected.** Review it, and the peak-season run-rate
  settings, in January 2027.
- **Never re-arm an automatic cut-off he has turned into a question.** The over-age order-log
  retirement is the standing example.

---

## Buying terms — check them, not just the price

VIPL buys on the **highest cash discount available**. Advance payment is acceptable *if it earns
the best CD*; advance at 0% CD is not. Read the payment-term line on every invoice and proforma
and flag it. ANL is on term Z554 = "100% Advance Payment as 0% CD" on ₹80 L/yr — worth ₹1.6–2.4 L
a year. CD/TOD/scheme never touches item cost, so a CD win never shows in the tool's margins.

---

## Reading the output

Dashboard: `07 REORDER OUTPUT/VIDIRA Reorder Dashboard.html`. Branch selector Burdwan /
Siliguri / Both, default Burdwan; Burdwan demand = `am − sdm`. Sales columns are **branch-scoped**
(`_bam`, `_bso`, `_bcm`, `_bpnd`) — never show company figures on a branch-scoped screen.
A **Pending** column sits immediately before ORDER in every order view.

Views include *Order — Burdwan*, *Order — Siliguri*, and **Add items** for each branch: every code
NOT currently on that branch's order, with an editable ORDER box, so Dinesh can introduce a line
the tool didn't suggest. MOQ is deliberately hidden on the Siliguri Add view — a Siliguri line can
be met by transfer in any quantity — and a **Can transfer** column shows what Burdwan can spare.

Report brand by brand. State what was held and why. If a figure surprises you, measure it a
second way before publishing it.