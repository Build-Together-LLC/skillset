# Privacy: keeping real people out of the video

A recording shows whatever the page shows. Pages fill lists and drop-downs by themselves, so real names
appear even when you only meant to show demo data. In the first build, the first assembled video had
real staff names in **three places**, none of which the storyboard asked for. A scan of the finished
video found them. This file is the procedure that prevents it.

## Rules

1. Record a copy of the app with demo data. Do not record production or a shared test site unless the user
   asks, and then only read-only scenes.
2. Real staff, parents, students, phone numbers, email addresses and keys must not be visible in any frame.
   A work email domain counts.
3. Do not type or show secrets. Passwords come from the environment.
4. Scan the finished video and fix every hit before sharing. Say in the hand-over that text recognition can
   miss small text.

## Where real data hides

| Place | Example from the build |
|---|---|
| "People who have items" chips | A row of host buttons on the console listed every host with sessions, including real staff |
| Drop-down lists that open on focus | The "Select employee" list showed all employees with their ids before anything was typed |
| Search lists with extra text | The slot search showed each slot's hosts in grey, so real names appeared in the list |
| A record's side panel or "Assigned To" | The user's own mailbox and others appeared in a card on the form |
| Linked-record cards | A booking card on a Lead showed the host name and three work email addresses |
| Dashboards and counters | Usually safe, but check names in "top" lists |
| Settings pages | A "contact" or "owner" email field, a fallback address, a subject mailbox |
| Dates and counts in the header | Harmless, but they reveal how real the data is |
| The browser tab, URL bar and notifications | The recording is the page only, but toasts can carry names |

Walk through every scene once yourself and ask: what does this list contain when it is full?

## Masking while recording (`config.scrub`)

`config.scrub` is a list of JavaScript snippets. They run every 150 ms on every page of every scene, so
elements that appear later (a drop-down, a card that loads late) are masked too. Typical rules:

```js
// hide drop-down options that are not demo people (employee ids, or slot options that list hosts)
document.querySelectorAll('.hostopt').forEach(o => {
  const x = o.innerText || '';
  if (/HR-EMP-(?!DEMO)/.test(x) || (/\bof \d+\b/.test(x) && !/Demo Counsellor/.test(x))) o.style.display = 'none';
});
// hide chips whose label is not a demo name
document.querySelectorAll('button').forEach(b => {
  const p = b.parentElement;
  if (p && p.querySelectorAll('button').length > 5) {
    const x = (b.innerText || '').trim();
    if (x && !/^(Demo |Reassign|Dismiss|Clear|Choose|Review|Next|Create|Back|Apply|Join)/.test(x)) b.style.display = 'none';
  }
});
// rewrite text nodes (names and emails) on a card
const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
for (let n; (n = w.nextNode());) n.nodeValue = n.nodeValue.replace(/\S+@your-school\.org/g, 'demo.user@example.com');
// rewrite input values
document.querySelectorAll('input').forEach(i => { if (/@your-school\.org/.test(i.value)) i.value = 'calendar.owner@example.com'; });
```

For things visible only at the very start of a scene, add the same code as a `pre` step. For things that
render again after you scroll or change a filter, a one-off `pre` is not enough: use `config.scrub`.

Prefer hiding or rewriting to blurring. Blur hints that something was hidden and can be partly legible.

## Scanning the finished video

```bash
$FLOWVIDEO_HOME/venv/bin/python scripts/ocr_scan.py --video out/video.mp4 --terms terms.txt --every 2
```

It reads a frame every 2 seconds and exits with 1 if a term is found, printing the second of each hit.
Open `out/video.mp4` at that second, find which scene it is, fix the mask, record that scene again,
assemble, and scan again. Scan only the part you changed with `--from 215 --to 315`.

### Building `terms.txt`

- Query the real names from the app's database (the people who can appear in the lists), then add each
  surname and distinctive first name of six letters or more. Short common words cause false hits.
- Add your email domain and a regular expression for any address that is not on the allowed example domain:
  `re:[a-z0-9._-]+@(?!example\.com)[a-z0-9.-]+`
- Keep `terms.txt` out of the repository: it is a list of real people. `examples/terms.example.txt`
  has placeholders only.

### Prove the scan works

Once per project, remove the mask from one scene and scan: it must report hits and exit with 1.
`examples/run-example.sh` does the passing side; the negative test is described in the README.

### Limits

Text recognition reads normal text well and misses very small, blurred or low contrast text and anything
inside an image. It cannot tell whether a name is real; the term list does. Treat it as a safety net under
the masking rules and the manual walk-through.

## The documents and the video must agree

If the video shows a configuration (services, settings, keywords), the same names should be in the written
guide. When recording a local copy, set it up to mirror the real site (same service names, same settings),
and tell the viewer in the narration that the screens are from the demo copy of that setup.

## Cleaning up

After the recording, delete the demo users, records, slots and bookings you made, restore the settings you
changed, remove the temporary login, and stop the servers and workers you started. Keep the cleanup scripts
with the seed scripts so the next recording starts from a known state.
