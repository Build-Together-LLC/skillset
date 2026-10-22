# Recording notes: what goes wrong and what to do

Everything here was met while building a 9 minute video (17 scenes) of a booking app. Frappe and ERPNext
specifics are in the last section.

## Before recording

| Check | Why |
|---|---|
| The app answers quickly: open a page with `curl -w "%{time_total}"` | A dev server that takes 10 seconds to load makes the first steps of a scene fail |
| Cache and queue services are running (for Frappe: both Redis servers) | When the queue Redis was down, desk pages returned 500 and loaded in 30 seconds. They die between sessions; check before each recording day |
| A background worker is running if the app does work in the background | Pressing "Create slots" only queued a job. With no worker, nothing was created and later scenes found no data. Start `bench worker --queue long` for that one queue only, so old jobs and emails do not fire |
| Demo data exists and matches the real configuration | The viewer should see the same names, settings and wording as the real site |
| One login for the recording, with the roles the flow needs | A System Manager sees all the sections. A plain user sees fewer. Record each role's view with a separate login if it matters |
| Chrome or Chromium is installed | `CHROME_PATH` can point to it. The tools use the system browser, not a downloaded one |

## Timing

- Step times come from the narration (`s` and `d`), so a slow step delays the next one but never the voice.
  If a scene's steps cannot finish inside its narration, lengthen the sentence or move steps to a later one.
- `ready` is the quiet time before the narration starts. Page load is not counted against the voice.
- The video is cut from the moment the narration starts (`offset` in `rec/<scene>/meta.json`), so the
  loading time at the start never appears.
- Navigations wait for `domcontentloaded`, not `load`. Desk pages with many assets take over 9 seconds to
  reach `load` and time out. `nav_timeout` is 45 seconds for the same reason.

## Selectors

| Trap | What happened | Do this |
|---|---|---|
| `:text-matches()` and `text=` match the smallest element holding the text | A list option made of two inner spans never matched as a whole | Match the option with `:has-text("...")` or pick by position `>> nth=1` |
| `:has-text("Online Counselling")` also matches "Demo Online Counselling" | The wrong service was chosen | Look at the option order once with a probe script, then use `nth` |
| The same input exists twice, one hidden | The click went to the hidden one and timed out | Add `:visible` |
| `input[aria-label^="Reassign"]` matches every row | The first row was used, which was the wrong session | Scope to a row: `tr:has-text("Thu 29 Oct") input[aria-label^="Reassign"]` |
| A multi-select input hides already chosen people from its list | Searching the second person by full name found nothing | Fill a short common word ("Demo Counsellor"), then click the option with `:has-text` |
| Elements added later (a button that appears after a check) | Click timed out | Give the earlier step a `wait`, or put the click on a later sentence |
| A link styled as a button | `button:has-text(...)` found nothing | Use `text=...` or the class of the element |
| Read-only date inputs | `fill` failed ("not editable") | Click the field, then click the day in the calendar popup |

To find the right selector, run a small Playwright script that opens the page, types or clicks, and prints
`innerText` and `className` of the candidates. Do this before writing the step.

## Highlights and the cursor

- A red box is drawn at the position the element had when the step ran. If the page then scrolls, the box
  stays behind in the wrong place. Add `{"do": "clear"}` before any click or scroll that moves the page.
- The cursor is a red dot. It moves only when a step moves the mouse (`move`, `click`, `fill`, `type`).

## Data and re-recording

- Recording changes the data. A second take of "create slots" finds the slots already there and shows a
  different preview ("already exist"). Delete what the scene made, then record it again.
- Names with counters change on each take (a slot called `...-002` becomes `...-003`). Scenes that point
  at such a name need the new value: store it in the placeholders and rebuild `flow.json`.
- If narration changes, the voice is generated again and its timing changes slightly. Record that scene
  again. If you regenerate every voice, record every scene again; scenes recorded against the old timing
  drift by a fraction of a second.
- Record one scene at a time while fixing it: `node record.js --project DIR s05`. Always read `last.png`
  of the scene to see where it ended.
- Pass scene ids in any order; scenes always run in the order of `flow.json`.

## Waiting for long jobs

Recording a full video takes about as long as its narration, plus loading. Run it in the background
with output to a log and wait on the log with an `until` loop that also ends when the process ends:

```bash
node record.js --project DIR > rec.log 2>&1 &
while ps aux | grep -q "[r]ecord.js"; do sleep 6; done; cat rec.log
```

A monitor that only waits for a final line hangs for its whole timeout if the recorder crashes.

## Frappe and ERPNext notes

- Desk fields can be targeted with `[data-fieldname="..."]`. Section headings and collapsed sections are
  not in the page until opened; highlight a field that is visible, or click the section first.
- The activity timeline (history, comments) is at the bottom of a form. Scroll with `{"do": "scroll", "y": 2200}`
  and highlight `.timeline-item:has-text("...")`.
- The first load of a form after a restart is slow. Use `ready: 4500` or more.
- Website pages (booking pages) use plain classes; test them as `guest: true`.
- The logo image of a site may return 403 and show a broken image icon. It is harmless; do not highlight it.
- Real data hides in lists that the page fills by itself: "hosts with sessions" chips, link drop-downs,
  the "Assigned To" box on a record, child tables, the sidebar. Check them first (`privacy.md`).
- A form's "Create" menu, dialogs and selects are Bootstrap widgets. For `<select>` elements set the value
  with an `eval` step and dispatch a `change` event.

## Audio and video

- `ffmpeg` comes with `imageio-ffmpeg`; Playwright also needs its own small ffmpeg to record
  (`setup.sh` installs it). If recording says "ffmpeg is not installed", run `setup.sh` again.
- The final pass lowers the loudness to -21 LUFS and resamples to 44.1 kHz. Without the resample, the
  loudness filter outputs 96 kHz audio.
