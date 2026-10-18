---
name: responsive-ui-walkthrough-media
description: Create, fix, audit, or publish instructional walkthrough media for web/app UI, including animated GIFs, screenshots, short videos, highlighted UI callouts, onboarding/tutorial embeds, and desktop/mobile responsive rendering. Use when the user complains that GIFs/screenshots are low quality, unreadable, cropped, misaligned, wrong, not working on phone/desktop, or when producing tutorial media that must be usable across viewports before publishing.
---

# Responsive UI Walkthrough Media

Use this skill for production-quality UI tutorial media. The goal is not “make a GIF”; the goal is “teach a user with a real rendered UI that works on desktop and mobile.”

## Hard rule

Never mark walkthrough media as done only because files uploaded and URLs return 200. Publish only after visual QC on at least:

- desktop viewport: about `1440x900` or the product’s real desktop width
- phone viewport: about `390x844` or the user’s target device size

If desktop UI is inherently too detailed for phone, choose a mobile-safe treatment instead of shrinking it: zoomed crops, horizontal scrollbox, fullscreen/tappable media, or video.

## Workflow

1. **Define the teaching objective**
   - For each asset, write the exact UI concept being taught: e.g. “click one row”, “use left filter panel”, “read child table”.
   - Do not use broad labels like “screen overview” unless the highlight actually covers an overview.

2. **Capture from the real UI**
   - Use real product screens, not mocked/synthetic UI, unless explicitly requested.
   - Capture at high resolution.
   - Capture desktop and mobile separately when the product layout differs.
   - Avoid using one desktop capture blindly for phone if it will become unreadable.

3. **Choose the right media treatment**
   - Use GIF for simple, short, low-detail loops.
   - Use MP4/WebM or embedded video for detailed ERP/admin screens, cursor motion, scrolling, or longer steps.
   - Use static annotated screenshots when motion does not add value.
   - For phone pages showing desktop/admin UI, prefer:
     - zoomed target crops, or
     - a fixed-width media scrollbox with clear “swipe sideways” instruction, or
     - a tappable fullscreen link.

4. **Place annotations correctly**
   - Instruction/callout card should not cover the UI being taught.
   - Highlight box must tightly but comfortably wrap the target, with padding.
   - Avoid ultra-thin strips unless the element itself is a thin control and still readable.
   - Do not draw arrows across important table text.
   - If a control is not visible, change the teaching step instead of pretending it is there.

5. **Make desktop and mobile both work**
   - Desktop: media should be large enough to read and should not force awkward scroll if avoidable.
   - Mobile: media should not shrink below readability; if scroll is intentional, only the media box should scroll, not the whole page.
   - Check for unrelated page overflow caused by fixed-width images inside grid/flex/wiki containers.
   - The page around the media must still be readable and not clipped.

6. **Publish with cache-busting**
   - Use versioned or hashed filenames for replacements (`-v2`, content hash, date stamp, etc.).
   - Update embeds to the new filenames.
   - Verify old cached assets are not the ones shown in the rendered page.

7. **QC before final reply**
   - Generate contact sheets from animated media: first frame plus key teaching frames.
   - Capture actual rendered page screenshots at desktop and phone sizes.
   - Use visual inspection and/or image analysis to check:
     - UI text readability
     - annotation overlap
     - highlight correctness
     - mobile clipping/overflow
     - desktop layout quality
   - Fix blockers before telling the user it is done.

## Quality gates

A walkthrough asset passes only if all are true:

- The highlighted UI element exactly matches the caption.
- The UI element is readable at the rendered size.
- The callout does not hide the UI element being explained.
- There is enough surrounding context to understand what screen the user is seeing.
- No “decorative” highlight covers a broad random region.
- Mobile does not crush a desktop UI into unreadable text.
- Desktop still looks intentional and not phone-compromised.
- The final page is inspected, not just the source asset.

## Useful bundled script

Use `scripts/qc_walkthrough_media.py` to create a local QC folder with:

- desktop and mobile screenshots of a URL using headless Chrome
- optional GIF contact sheets using ffmpeg
- a small JSON summary of generated files

Example (`SKILL_DIR` is this skill's own directory, wherever it is installed):

```bash
SKILL_DIR=$(dirname "$(find ~/.claude/skills .claude/skills -name SKILL.md -path '*responsive-ui-walkthrough-media*' 2>/dev/null | head -1)")

python3 "$SKILL_DIR/scripts/qc_walkthrough_media.py" \
  --url https://example.com/tutorial \
  --gif path/to/walkthrough.gif \
  --out /tmp/tutorial-qc
```

Then inspect the PNG/JPG outputs visually or with the image tool before publishing.

## Common failure modes

- “HTTP 200 verified” but the rendered image is unreadable.
- Desktop screenshot embedded at `width:100%` gets crushed on phone.
- Fixed-width image widens the whole mobile page instead of only scrolling inside its own container.
- Highlight coordinates are mathematically correct on the source image but wrong after crop/resize.
- Caption says “filters” while highlight points to column headings or toolbar.
- Callout card overlaps the real content.
- Thin highlighted row/filter strips teach nothing because users cannot read them.
- Desktop gets worse while trying to fix mobile.

## Recommended final report

Keep the user-facing completion note concise, but include evidence:

- pages checked
- viewport sizes checked
- assets replaced/versioned
- specific issues fixed
- any remaining limitation, if real
