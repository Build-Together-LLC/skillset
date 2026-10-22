# Review and privacy checklist (run before every hand-over)

## Look at every picture, in batches
`contact_sheet.py sheet.png a.png b.png ...` puts up to 12 images on one view. Open each sheet and check:
- blank or half-loaded pages (a form that did not render, a spinner), stray popups, a banner covering the thing you are showing
- the title or the first column cut off by the crop; the picture too small to read at the width it will have
- the wrong data: real names, real counts, a list showing other people's records, a test user from another run
- numbers on a screenshot that the text does not explain, or text that points to a number that is missing
Open anything annotated at full size once.

## Where real data leaks in practice (all happened)
- **Suggestion and assignee lists** that draw from the whole site (cover-for colleagues in an e-mail, host pickers, "Assigned to").
  Pixelate the line (`annotate.py` `pixelate`) or choose a view that lists only demo users.
- **Sidebars and workspace lists** show every installed app and workspace. Crop the sidebar off.
- **Shared dev databases**: totals on a dashboard, list views without a filter, recent activity. Filter by a demo prefix in the URL.
- **URLs and hostnames** in chat bubbles, e-mails and forms: replace with an example domain (`chat_mock.py` has `replace`).
- **E-mails rendered from a queue** show recipients and sometimes colleagues. Check the whole message, not the top.
- **Test-suite leftovers** on a dev site (records named Tester, settings reset by tests).

## Scan the document
`privacy_scan.py doc.docx --deny names.txt` finds e-mail domains that are not examples, tokens and keys, and any word on your
deny list (put in it every real name and number you saw while shooting, one per line). It also lists external links: open each.
It cannot read pictures, so the contact sheets above are not optional.

## Rendering
- `render_check.sh` can take three minutes or more for a 50 page file, and a second conversion hangs if a LibreOffice process is stuck. Run it in the
  background with output to a log and wait on the log with an `until` loop that also ends when the process ends. If a conversion hangs, stop the stuck
  `soffice.bin` by name (`pkill -x soffice.bin`), never by `-f` pattern, then run it again.
- Check the page count of both files after every rebuild, and open the pages that changed, not only the first sheet.

## Layout
- Read every rendered page. Fix: a heading alone at the bottom of a page, a table split after one row, a table pushed onto a
  page by itself, an almost empty page before a forced page break, a diagram cut at the right edge (widen it in its plan),
  a tall screenshot that pushes its caption to the next page (`img(max_h=...)`).
- Count pages and compare with what you expected (a deck is about one page per slide).
- Numbers in figures match numbers in tables; every `{fig:x}` and `{tbl:x}` resolved; section cross references still point to the right section after renumbering.

## Wording
- If the user asked for no em dashes, search the generator for the long dash and the spaced hyphen before building.
- Say "not verified" where that is true. Say what version and date the guide was checked against.
