# Flow Video Builder

Make a narrated video of a whole product flow, the way a person would demonstrate it: the real app on
screen, a moving cursor, red boxes around what is being explained, dark scene cards, and a calm voice that
says what is happening. You write the story as a list of scenes; the tools record, voice and join them.

Built and proven on an appointment-booking web app: 17 scenes, 84 sentences, 9 minutes 12 seconds,
recorded from a demo copy of the site, scanned for real names, and checked before sharing. The full story
is in [references/case-study.md](references/case-study.md).

## What you get

| Output | File | Notes |
|---|---|---|
| The video | `out/video.mp4` | 1440 x 900, 30 fps, AAC audio at 44.1 kHz, a soft subtitle track inside |
| Subtitles | `out/video.srt` | One line per sentence, timed to the voice |
| Transcript | `out/transcript.md` | The narration by scene, ready to paste into a guide |
| Per-scene pieces | `rec/<scene>/` | The raw recording, the last frame (`last.png`), timing |

## Is this the right skill?

| You want | Use |
|---|---|
| A narrated video of the real app, scene by scene | **this skill** |
| A written guide or a slide-style document with screenshots | `demo-doc-builder` |
| A short GIF, a tutorial clip, or responsive media for a help page | `responsive-ui-walkthrough-media` |

A slide video (screenshots with captions) is not what this builds. If someone says "video of the flow",
they usually mean a real recording.

## Requirements

- Python 3.10+ with `venv`, Node 18+ with `npm`, and Chrome or Chromium. Tested on Linux (Ubuntu); the macOS browser and font paths are included but not tested.
- About 600 MB of disk for the tools and one voice. No GPU and no account.
- The app you will record, running on a copy with demo data.

## Install and test (once)

```bash
bash skills/flow-video-builder/scripts/setup.sh                 # tools go to ~/.cache/flow-video-builder
bash skills/flow-video-builder/examples/run-example.sh          # builds a 20 second sample and scans it
```

The test must end with `scanned N frames, 0 with hits` and `OK: .../out/video.mp4`.
Use another folder for the tools with `FLOWVIDEO_HOME=/path`, and another browser with `CHROME_PATH=/path`.
To make Claude Code find the skill everywhere: `ln -s <repo>/skills/flow-video-builder ~/.claude/skills/flow-video-builder`.

## Make a video

```bash
S=skills/flow-video-builder/scripts
T=${FLOWVIDEO_HOME:-$HOME/.cache/flow-video-builder}

python3 $S/new_project.py my-video --base http://localhost:8000 --login   # starter flow.json and terms.txt
#  edit my-video/flow.json: scenes, narration, steps  (references/storyboard.md)
export DEMO_USER=...  DEMO_PASSWORD=...                                  # never write these into flow.json

$T/venv/bin/python $S/tts.py       --project my-video                    # the voice
node               $S/record.js    --project my-video                    # the recordings
$T/venv/bin/python $S/assemble.py  --project my-video                    # video, subtitles, transcript
$T/venv/bin/python $S/ocr_scan.py  --video my-video/out/video.mp4 --terms my-video/terms.txt   # privacy scan
```

Record one scene again with `node record.js --project my-video s05`. Fix `step failed` lines first; open
`rec/s05/last.png` to see where the scene ended.

## The project folder

```
my-video/
  flow.json        you write this
  terms.txt        words that must never appear (real names, email domain). Keep it out of git
  audio/           one WAV per scene and timing.json (made by tts.py)
  rec/<scene>/     raw recording, last.png, meta.json (made by record.js)
  out/             video.mp4, video.srt, transcript.md (made by assemble.py)
```

## flow.json in one minute

```json
{
  "config": {"base": "http://localhost:8000", "voice": "en_US-amy-medium", "speed": 1.14,
             "login": {"url": "/login", "fill": {"#login_email": "${DEMO_USER}", "#login_password": "${DEMO_PASSWORD}"}, "submit": "#login_password"},
             "scrub": ["/* JavaScript that hides real names, run every 150 ms */"]},
  "scenes": [{
    "id": "s01", "title": "Create a booking", "url": "/app/booking/new", "ready": 4000,
    "narr": ["Open a new booking.", "Choose the service.", "Press save, and the booking is made."],
    "steps": [
      {"s": 1, "do": "click", "sel": "[data-fieldname='service'] input"},
      {"s": 1, "d": 1.2, "do": "type", "sel": "[data-fieldname='service'] input", "val": "School Visit"},
      {"s": 2, "do": "click", "sel": "button:has-text('Save')"}
    ]}]
}
```

`"s": 1` means "when the second sentence starts". `"d": 1.2` adds a second and a bit. That is the whole
timing model. Every setting, step type and chat step is in [references/storyboard.md](references/storyboard.md).

## Scripts

| Script | What it does |
|---|---|
| `scripts/setup.sh` | Makes the tools folder: Piper voice, ffmpeg, browser driver, text recognition |
| `scripts/new_project.py` | Starter project |
| `scripts/tts.py` | Voice for each scene, with sentence start times. Keeps audio of scenes whose text did not change |
| `scripts/record.js` | Records each scene in a real browser, running each step at its sentence |
| `scripts/assemble.py` | Title cards, recordings, voice, subtitles, loudness |
| `scripts/ocr_scan.py` | Reads the finished video and fails if a forbidden word is on screen |
| `scripts/maya1_tts.py` | Same job as `tts.py` with the Maya1 model on a GPU (not run yet) |
| `templates/chat.html` | WhatsApp-style chat replay for messaging scenes |

## Examples

| Path | What it shows |
|---|---|
| `examples/demo.html`, `examples/flow.example.json`, `examples/run-example.sh` | A 2 scene sample that needs nothing but a browser. It also uses a mask rule, and the scan proves the mask worked |
| `examples/chat-flow.example.json`, `examples/run-chat-example.sh` | A chat scene (messages, buttons, a list sheet) replayed in a phone frame with `templates/chat.html`. Needs only a browser |
| `examples/terms.example.txt` | How to write a terms list for the privacy scan |

## Before you share the video

1. Every scene recorded with no `step failed` lines, and each `last.png` looks right.
2. Frames checked from every scene.
3. `ocr_scan.py` reports 0 hits, and you have walked through the lists and drop-downs yourself
   ([references/privacy.md](references/privacy.md)).
4. The voice was listened to. The tools check length, loudness and silence, not how it sounds.
5. Demo data and logins removed, servers and workers stopped.

## Prove the scan works (once per project)

Remove `config.scrub`, record one scene, assemble and scan with a term that appears on that page. The scan
must print `HIT` lines and exit with 1. Then put the mask back and see 0 hits. The sample project was
checked this way: with the mask, 0 hits in 11 frames; without it, the name was found in 4 of 5 frames.

## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| `Executable doesn't exist ... ffmpeg` while recording | Playwright's recorder is missing | Run `setup.sh` again |
| `No Chrome or Chromium found` | Browser path | Install one or set `CHROME_PATH` |
| `step failed ... Timeout` on a click | Wrong or hidden selector, or the page is slow | Probe the page, add `:visible`, use `nth`; raise `ready` |
| `page.goto: Timeout` | Slow server | Raise `nav_timeout`; check the app's background services |
| Pages show 500 or load very slowly | A service the app needs is down (cache or queue) | Start it, then record again |
| A button press changes nothing | The app does the work in a background worker | Run the worker for that queue |
| Red box in the wrong place | The page scrolled after the box was drawn | `{"do": "clear"}` before the click |
| Voice and picture a little apart in an old scene | The narration was regenerated after it was recorded | Record that scene again |
| `No audio timing for sNN` | `tts.py` was not run for that scene | Run `tts.py` |
| Many `Missing phoneme` lines from Piper | Unusual characters in the narration | Harmless; reword if a word sounds odd |
| Audio is 96 kHz | Old assemble without the resample | Use this version |

## Related

- `demo-doc-builder`: the written guide and the slide-style demo for the same product.
- `responsive-ui-walkthrough-media`: short clips and GIFs.
- Detail: [storyboard](references/storyboard.md), [recording notes](references/recording-notes.md),
  [privacy](references/privacy.md), [voices](references/voices.md), [case study](references/case-study.md).
