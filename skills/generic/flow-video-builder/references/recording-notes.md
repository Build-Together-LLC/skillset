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

## Flows that change data

- **Script the whole run.** Write one `chain.sh` that resets the demo data, works out the names the new records will get, rebuilds `flow.json`, records the
  scenes in order and runs a small helper between scenes (`prep.py before_swap`, `before_deny`) for records that are not worth clicking through again
  (`templates/chain.example.sh`). A scene that changes data cannot be taken twice. Fixing scene 9 meant resetting and taking scenes 8 to 13 again, so keep the chain one command.
- **Names move.** A naming series keeps counting after a reset. Read the series value after the reset, write the expected names to `names.json`, and have
  `flow.py` read it. For records made earlier in the same run, open them from the list instead: url `/app/<doctype>?<field>=<full name>` and a `pre` step
  that clicks the row.
- **Keep spare subjects.** When a take leaves a record in a state you do not want (a reason already typed, a review history with two rows), the next take
  needs another fictional record. Seed more records than the story uses.
- **Search boxes match inside words.** Typing `Ria` picked `Maria`. Type the full name or the id.
- **A scene is slower than its narration, never faster.** `record.js` prints one line at the end of each scene, and a scene takes the narration plus 7 to 20 seconds
  of page load. Silence for a few minutes is normal. Check that the `.webm` in `rec/<scene>/` is growing before you stop it, and wait on a log marker with an
  `until` loop in a background command, not on a timer.

## Timing: steps run one after another

- A step starts at its sentence time plus `d`, or as soon as the step before it has finished, whichever is later. Typing a name, waiting for the form to fill,
  choosing a value and saving takes 10 to 14 seconds. If those steps are attached to sentence 1 and sentence 2 describes the result, the picture is 10 seconds
  behind the voice. Attach the whole chain to sentence 0, keep the in-step waits short, and let the sentence that describes the result start after it.
- After recording, check the timing instead of trusting it: read `audio/timing.json` for the start of each sentence, cut a frame at those times with the
  bundled ffmpeg (`ffmpeg -ss <offset + t> -i rec/<scene>/*.webm -frames:v 1 f.png`, offset from `meta.json`) and look at it.
- Contact sheets of the finished video (`ffmpeg -vf fps=1/12,scale=480:300,tile=4x4`) show a wrong highlight, a leftover popup or a loading splash in four looks.

## Pages that surprise you

- **Background jobs finish after the page loaded.** A comment written by a job is not on the open form. Reload (`eval` `location.reload()`, then `wait`), scroll to
  the bottom with `scroll` `y: 8000`, then highlight. A scroll of 1800 px stopped halfway.
- **A save re-renders the form.** Collapsed sections that you opened close again. Open them again before the next highlight, or the red box lands on whatever now
  sits at that position.
- **A `pre` step that throws ends the scene.** Steps in `steps` only print `step failed`, but `pre` is not caught. Use `eval` with optional chaining for things
  that may or may not be there: `[...document.querySelectorAll('button')].find(b=>/Skip tour/.test(b.innerText))?.click()`.
- **First-visit tours.** A single page app may open a "Step 1 of 9" overlay in every fresh browser context. Dismiss it in `pre`.
- **A screen that hides a button from the demo login.** The recording login must hold the roles the screen checks. Ask whether the button is missing for the demo
  user or for everyone. In one app it was missing for everyone (a bug), which became a scene of its own.
- **Show a gap honestly.** When the screen cannot do something, record the missing button, then do it through the app's own API from the page
  (`eval` `frappe.xcall('<method>', {...}).then(() => location.reload())`), say so in the narration, and show the result. Do not fake the click.
- **Duplicate toolbars.** `locator.first()` can pick a hidden duplicate and time out. Add `:visible`, and prefer a class (`button.btn-primary:visible`) to `>> nth=1`.
  Link-field options are `ul[role=listbox]:visible div[role=option]`.
- **A list view remembers its last filter** per user. Give the url an explicit filter before you shoot it.
- **Accept the "unsaved changes" prompt** when you leave a new form (`page.on('dialog', d => d.accept())`). Dismissing it cancels the navigation.
