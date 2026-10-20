---
name: markitdown-convert
description: >
  Converts files to Markdown using the local `markitdown` CLI tool.
  Use this skill whenever the user attaches a file (PDF, DOCX, XLSX, PPTX, HTML,
  image, audio, etc.) and asks to convert it to Markdown — even if they phrase it
  casually: "turn this into markdown", "convert this file", "make this a .md",
  "markitdown this", or simply attaches a file and says "convert". Always trigger
  this skill rather than trying to convert the content manually.
---

# markitdown-convert

Convert a file to Markdown using the `markitdown` CLI, then save the result as a
`.md` file with the same base name.

## How it works

`markitdown` accepts a file path (or URL) and writes Markdown to stdout.

```
markitdown <input_path> > <output_path>
```

If it is not installed, tell the user to run `pip install 'markitdown[all]'` and stop.
Do not fall back to converting by hand.

## Step-by-step

1. **Find the file.**
   Use the path the user gave. If they only named the file, look in the current
   working directory first. If it still can't be found, ask for the path.

2. **Derive the output path.**
   Strip the extension and append `.md`, in the **same folder as the input** unless the
   user asked for a different folder. Never overwrite an existing `.md` without asking.

   Example: `~/Downloads/report.pdf` → `~/Downloads/report.md`

3. **Run the conversion.**
   Quote both paths — file names often contain spaces.
   ```bash
   markitdown "<input_path>" > "<output_path>"
   ```

4. **Check for errors.**
   If the command fails (non-zero exit code) or the output file is empty, delete the
   empty file and tell the user what went wrong. Common causes: unsupported file type,
   `markitdown` not on PATH, or a missing optional extra (e.g. audio needs
   `markitdown[audio-transcription]`).

5. **Confirm briefly.**
   One sentence with the output path: "Converted `report.pdf` → `~/Downloads/report.md`."
   No need to summarise the content unless the user asks.

## Notes

- If the user hasn't given a file yet, ask for one before proceeding.
- If several files are given, convert each and list every output path together.
- Do not try to do the conversion manually (e.g. by reading and rewriting the
  content yourself) — always run `markitdown`.
