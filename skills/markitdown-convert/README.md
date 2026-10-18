# Markitdown Convert

Point Claude at a file. Get back the same file as Markdown.

## What it does

Converts PDFs, Word, Excel, PowerPoint, HTML, images and audio to Markdown using Microsoft's
[`markitdown`](https://github.com/microsoft/markitdown) tool. Markdown is easier to search, diff,
paste into a PR, or give to Claude as context.

The conversion is always done by the tool — **Claude never retypes the content itself**, so nothing
gets reworded or left out along the way.

## What you need

- Claude Code with this skill installed.
- `markitdown` on your PATH:

  ```bash
  pip install 'markitdown[all]'
  ```

  If it's missing, Claude tells you and stops — it won't try to convert by hand.

## How to use it

```
convert ~/Downloads/fee-structure.pdf to markdown
```

```
markitdown these: report.docx, budget.xlsx
```

## What you get

A `.md` file with the same name, **in the same folder as the original**:

| Input | Output |
|---|---|
| `~/Downloads/report.pdf` | `~/Downloads/report.md` |
| `./budget.xlsx` | `./budget.md` |

Want it somewhere else? Just say where. An existing `.md` with the same name is never overwritten
without asking.

## Common problems

| You see | What it means |
|---|---|
| `markitdown: command not found` | Install it: `pip install 'markitdown[all]'` |
| Output is empty | The file type isn't supported, or the file is a scanned image with no text layer |
| Audio file fails | Audio needs an extra: `pip install 'markitdown[audio-transcription]'` |

## For developers

- `SKILL.md` — the instructions Claude follows: finding the file, naming the output, and error
  checks.
