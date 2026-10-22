# Case study: a complete-flow video for a booking app

How this skill came about, in order, so the next video can reuse the decisions.

## The request

"A complete flow video representation, with audio for the complete transcript." The product was an
appointment booking app for school admissions (visit and online meeting bookings, on a chat channel and on a
booking page). A written guide and a presentation-style demo already existed. The user wanted a video of
the same flow with a soft female voice.

## Attempt 1: a slide video (rejected)

The first video turned the guide's screenshots into 28 slides with captions and a male voice (8 minutes).
The user answered: "you don't have to create the video of presentation, you have to create a video of
complete flow", and pointed to a reference video.

Lesson: when the user says "video of the flow", record the real product, not slides. Ask for, or find, the
reference before building anything.

## Reading the reference

The reference was an 8 minute screen recording of another feature (click-to-call from a CRM Lead). Frames
every 6 seconds showed its structure:

- a dark navy title card with the scene name and "Scene 01" (about 2 seconds),
- the real application, in a 1440 x 900 browser window,
- a red box around the element being discussed,
- voice-over (the audio itself was not transcribed).

That became the format of the skill: scene cards, real recordings, red boxes, voice.

## Decisions

| Decision | Why |
|---|---|
| Record a local copy with demo data, set up like the staging site | The user wanted the screens and configuration to match the staging site. Writing demo bookings and slots to a shared site, and showing its real staff, was not acceptable. The local copy already had the same services, policy and locations, and the chat settings were set to the staging values for the recording |
| Piper "Amy" voice | Soft, offline, no GPU. Maya1 was requested but needs a GPU; the machine had none |
| Sentence-keyed steps | Each action is scheduled to the sentence that mentions it, so the picture follows the words |
| Chat replay in HTML for the messaging channel | A real phone cannot be recorded; the real message text is replayed in a phone frame |
| Explain the "why" | The user asked why bookings sit on the customer record and why leave and holidays matter. Two short scenes were added next to the screens that show them |

## Build log

1. Analysed the reference video; wrote the first storyboard of 14 scenes (about 70 sentences).
2. Built `tts.py`, `record.js`, `assemble.py`, `chat.html`.
3. Playwright could not record: its own ffmpeg was missing. `playwright install ffmpeg` fixed it.
4. Pages failed with 500 and took 30 seconds: both Redis servers had died. Restarted them.
5. Selectors failed in the console (list options, the second person in a multi-select, a read-only date
   field). Probed the page with small scripts and fixed each step.
6. "Create slots" queued a background job and nothing happened: no worker. Started a worker for the one
   queue, then deleted the slots and recorded the scene again so the preview was clean.
7. Narration changed for some scenes; the voice was regenerated for all of them, so earlier recordings were
   a fraction of a second out of step. Added audio caching by narration hash and recorded those scenes again.
8. Matched the staging site's wording: services and settings that look the same, plus the two "why" scenes.
9. Assembled: 17 scenes, 84 sentences, 9 minutes 12 seconds, 1440 x 900, with a subtitle track.
10. **Scanned the video by text recognition.** It found real staff names in three places: host chips on
    the console, the employee drop-down, and the slot search list (plus a customer card with work emails, found
    by looking). Added `config.scrub`, recorded the affected scenes again, scanned again: no hits.
11. Cleaned up the demo data, stopped the servers, copied the video, subtitles, transcript and scripts to the
    documents folder.

## Numbers

- 17 scenes, 84 sentences, about 550 seconds, 18 MB.
- Recording took about as long as the narration plus loading; a full re-record of everything is 15 to 20 minutes.
- First scan: 9 frames out of 276 had real names. Second scan of the changed part: 0 of 50.

## What to reuse

- `examples/chat-flow.example.json`: a chat scene with every chat step type.
- The scrub rules written out in `references/privacy.md`.
- The order: setup screens, then the staff tools, then the customer's side, then staff booking, then the
  "why" scenes, then the settings that must be checked before going live.

## What was not verified

The audio was checked for length, loudness and silence, not by listening. The Maya1 script was not run.
Say so in the hand-over.
