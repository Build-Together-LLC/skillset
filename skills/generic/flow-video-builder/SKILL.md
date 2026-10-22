---
name: flow-video-builder
description: >
  Build a narrated screen-recorded video of a complete product flow: real browser recordings of
  the app with a moving cursor and red highlight boxes, dark scene title cards, WhatsApp-style
  chat replays for messaging steps, a soft offline voice-over (Piper, or Maya1 on a GPU) that is
  synchronised to the clicks, burned-in subtitle track, and a text scan of the finished video for
  real names and emails before it is shared. Trigger on: "make a video of the flow", "screen
  recording with voice over", "walkthrough video with narration", "demo video of the whole
  process", "video version of the guide", "record the flow with a female voice", "like the
  reference video" (when the reference is a screen recording with scene cards). Not for slide
  decks or documents (use demo-doc-builder) and not for short GIFs or tutorial clips (use
  responsive-ui-walkthrough-media).
---

# Flow Video Builder

Turns a storyboard (`flow.json`) into one MP4: for each scene the real app is driven in a browser
while a voice explains it. Every click, highlight and typed word is scheduled to the sentence that
mentions it, so picture and voice cannot drift.

Read `README.md` for the folder layout and a first run. This file is the working procedure.

## Hard rules

1. **Record a throwaway copy, never production or a shared test site**, unless the user says so.
   Use demo data and mirror the real configuration (names, settings) so the screens look the same.
   Reading real settings is fine; creating, changing or deleting data on a shared site is not.
2. **No real people in the video.** Real staff, parents, students, emails and keys must not appear.
   Mask them in the page while recording (`config.scrub`), then run `scripts/ocr_scan.py` on the
   finished video. A scan hit means fix the scene and record it again.
3. **No secrets on disk.** Passwords go in the environment (`"${DEMO_PASSWORD}"` in `flow.json`).
4. **Keep the user's own Python environment clean.** The tools live in `$FLOWVIDEO_HOME`
   (default `~/.cache/flow-video-builder`), made by `scripts/setup.sh`. Never `pip install` the voice
   or video packages into a project or bench environment.
5. **Narration is plain words.** Short sentences, no em dashes, say what is on the screen and why it
   matters. Spell out letters that must be read aloud ("S M S").

## Procedure

1. **Set up once:** `bash scripts/setup.sh` (voice, ffmpeg, browser driver). Check with
   `bash examples/run-example.sh`; it builds a 20 second sample and runs the privacy scan.
2. **Agree the flow.** Ask for (or read) the reference: a guide, a PRD, an earlier video. Write the
   scene list: one idea per scene, 15 to 40 seconds each, in the order a newcomer would meet it.
   Say if a "why" scene is needed (why a rule exists) and put it next to the screen that shows it.
3. **Prepare the data.** Seed demo data, start the app, create a login for the recording, and make
   sure any background worker the app needs is running (see `references/recording-notes.md`).
4. **Write `flow.json`** (`references/storyboard.md` has the schema and every step type). Narration is a
   list of sentences; a step says which sentence it belongs to with `"s": index`.
5. **Voice:** `python scripts/tts.py --project DIR`. Unchanged scenes keep their audio.
6. **Record:** `node scripts/record.js --project DIR [sceneId ...]`. Read every `step failed` line.
   Open `rec/<scene>/last.png` to see where a scene ended. Fix selectors, record only that scene again.
7. **Assemble:** `python scripts/assemble.py --project DIR` gives `out/video.mp4`, `video.srt`, `transcript.md`.
8. **Check:** play frames from each scene (extract with ffmpeg), then
   `python scripts/ocr_scan.py --video out/video.mp4 --terms terms.txt`. Build `terms.txt` from the real
   names that exist in the data (see `references/privacy.md`).
9. **Clean up** the demo data and stop the servers and workers you started. Tell the user where the
   files are, the length, which voice was used, and anything not verified (for example: not listened to).

## When the narration changes

The voice is random each time it is generated. If a scene's narration changes, its audio and timing
change, so record that scene again. `tts.py` skips unchanged scenes for exactly this reason. If you
regenerate everything, record everything again.

## Voices

Default is Piper `en_US-amy-medium` slowed to 1.14 with low noise, which sounds calm and soft.
`references/voices.md` lists other voices and the Maya1 route (needs a CUDA GPU, not tested here).

## Waiting

Recordings take about as long as the narration. Run long commands in the background and wait on the log
with a Monitor `until` loop that also stops when the process exits. Do not poll with `sleep`.

## Files

- `scripts/setup.sh`, `tts.py`, `record.js`, `assemble.py`, `ocr_scan.py`, `maya1_tts.py`
- `templates/chat.html`: WhatsApp-style chat replay page for messaging scenes
- `examples/`: sample page, sample `flow.json`, `run-example.sh`
- `references/`: storyboard schema, recording notes, privacy, voices
