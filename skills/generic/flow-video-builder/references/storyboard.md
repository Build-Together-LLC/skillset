# Storyboard: writing flow.json

`flow.json` is the only file you author. It has a `config` block and a list of `scenes`.
`python scripts/new_project.py DIR` makes a starter; `examples/flow.example.json` is a two-scene sample and
`examples/chat-flow.example.json` shows the chat steps.

## config

| Key | Default | Meaning |
|---|---|---|
| `base` | empty | Prefix added to relative `url` values, for example `http://localhost:8000`. Absolute `http(s)://` and `file://` URLs are used as they are |
| `viewport` | 1440 x 900 | Recording size. Keep the product's real desktop width; the video is encoded at this size |
| `login` | none | `{url, fill: {selector: value}, submit: selector, wait: ms}`. Values may contain `${ENV_NAME}`, read from the environment, so no password is written down. Done once; the session is reused by every scene |
| `voice` | `en_US-amy-medium` | Piper voice name. See `voices.md` |
| `speed` | 1.14 | Piper `length_scale`. Higher is slower. 1.10 to 1.20 sounds calm |
| `noise`, `noise_w` | 0.45, 0.55 | Piper variation. Lower is steadier |
| `volume` | 0.9 | Piper volume before the final loudness pass |
| `scrub` | none | List of JavaScript snippets run in the page every 150 ms on every scene. Use them to hide or rewrite anything private. See `privacy.md` |
| `timeout` | 9000 | Milliseconds a step waits for its element |
| `nav_timeout` | 45000 | Milliseconds a page load may take. Slow dev servers need this |
| `cards` | true | Dark title card before each scene |
| `card_seconds`, `card_color` | 2.4, `[27,42,74]` | Card length and background colour |
| `loudnorm` | `I=-21:TP=-2:LRA=9` | Final loudness target. -21 is soft; the usual spoken-word value is -16 |

## scene

| Key | Meaning |
|---|---|
| `id` | Short unique name. Used for file names and to record one scene again |
| `title` | Shown on the title card and in the transcript |
| `narr` | List of sentences. One sentence, one idea. This is the voice-over |
| `url` | Page to open first |
| `steps` | Actions, each tied to a sentence (below) |
| `pre` | Steps run after the page loads but before the narration starts. Use for hiding things that are visible at the very start |
| `ready` | Milliseconds to wait after the page opens before the narration starts. Default 3500. Give slow pages 5000 |
| `guest` | `true` records without the login. For public pages |

## steps

Every step has `do` plus its own fields, and when to run it:

- `s`: index of the sentence it belongs to (0 is the first). It runs when that sentence starts.
- `d`: extra delay in seconds after the sentence starts. Several steps on one sentence use rising `d` values.

A step that fails is printed (`step failed ...`) and the scene carries on, so the video is still made.

| `do` | Fields | What it does |
|---|---|---|
| `goto` | `url`, `wait` | Open another page |
| `hl` | `sel`, `pad`, `keep` | Draw a red box around the element and scroll it into view. A new `hl` replaces the old box unless `keep` is true |
| `clear` | | Remove the red boxes. Do this before a click that scrolls the page |
| `move` | `sel` | Glide the cursor to the element |
| `click` | `sel`, `wait` | Move, then click |
| `fill` | `sel`, `val` | Click and set the value at once |
| `type` | `sel`, `val` | Click and type slowly, 70 ms a key. Use for the words the viewer should see being typed |
| `press` | `key` | Press a key |
| `scroll` | `y` | Smooth scroll by pixels |
| `scrollTo` | `sel` | Scroll an element into view |
| `eval` | `js` | Run JavaScript in the page. For selects, masks and anything the UI does not offer |
| `wait` | `ms` | Pause |
| `say`, `tap`, `openList`, `pick`, `side` | | Chat replay steps for `templates/chat.html` (below) |

`sel` is a Playwright selector: CSS, `text=...`, `:has-text("...")`, `:visible`, `>> nth=1`.
`recording-notes.md` lists the selector traps.

## Writing the narration

- 15 to 40 seconds per scene. About 12 to 15 characters per second at the default speed.
- Short sentences. Plain words. No em dashes. One idea per sentence, because each sentence is a
  place where the picture can change.
- Say what the viewer sees, then why it matters. "Tick Create Google Meet Links, and every online
  slot gets a Meet link."
- Spell out letters that must be read aloud: write "S M S" and "B F Funnel Settings".
- Put a "why" scene beside the screen that shows the rule. In the booking app video, "Why leave and
  holidays are checked" sits after the screen that creates slots, and "Why the booking sits on the customer record" after the staff booking screen.
- Do not read field values the viewer cannot see. Do not read secrets.

## Chat scenes (WhatsApp style)

For messaging steps there is no real phone to record, so `templates/chat.html` replays the real message
text in a phone frame. Set the scene `url` to `file://.../templates/chat.html` and use:

| `do` | Fields | Effect |
|---|---|---|
| `side` | `a`, `b` | Heading and caption on the left of the phone |
| `say` | `side` (`in` or `out`), `text`, `btns` | A message bubble; `btns` adds tappable buttons under it |
| `tap` | `title` | Highlight the button with that title |
| `openList` | `title`, `rows` (`[[label, subtitle], ...]`) | Open the list sheet |
| `pick` | `i` | Select row `i`, close the sheet, send it as the reply |

Use the exact strings the app produces (call its message-building function and copy the output) so the
chat is true to the product. Use dummy links such as `https://school.example.com/...`.

## Order of scenes

Scenes that change data must be recorded in the order a person would do it. For example, create the
slots, then reassign one, then show the slot's history. Scenes that only read can be recorded in any
order. Record the scenes that create data last when you are still adjusting the earlier ones, or reset
the data between takes (`recording-notes.md`).

## Placeholders in samples

`examples/chat-flow.example.json` uses `{{SKILL_ROOT}}` for the folder of the skill. `examples/run-chat-example.sh`
replaces it with `sed` before running. Use the same trick for any value that exists only after demo data is made
(a booking link, a record name): put `{{NAME}}` in `flow.json` and fill it with `sed` or a small script.
