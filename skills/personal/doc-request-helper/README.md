# Document Request Helper

Paste a Project Document Request. Get back a client-friendly description and step-by-step upload
instructions for every document in it.

## What it does

When we ask a school for documents — fee structures, student lists, staff data — each item needs a
**description** (what it is and why we need it) and **instructions** (how to fill the sample file and
upload it). Writing these by hand for every item is slow and uneven.

You give Claude the JSON of a Project Document Request, plus the sample files if you have them. The
skill:

1. Reads every item in `request_documents`.
2. Opens each sample file — Excel sheets and columns, PDF sections, Word headings — so the
   instructions name the **actual** columns the client has to fill.
3. Writes a 2–4 sentence description and 4–8 numbered instructions per item.
4. Puts it all in one `.txt` file, ready to copy into the description and instruction fields.

It is written for a school admin or operations head, **not a developer** — no "DocType", "API" or
"field type".

## What you need

- Claude Code with this skill installed.
- The Document Request JSON. Sample files are optional but give much better instructions.

## How to use it

```
generate upload instructions for this request
{ "doctype": "Project Document Request", "name": "DOC-REQ-0042", ... }
```

Pasting the JSON together with sample files is enough — you don't have to ask.

## What you get

A file named `<RequestID>_instructions.txt`, saved in your current folder unless you ask for another
one:

```
===============================================
DOCUMENT REQUEST: DOC-REQ-0042
PROJECT: Bhartiyam International School
CLIENT: ...
===============================================

-----------------------------------------------
ITEM 1: Fee Structure
Mandatory: Yes
Sample File: Fee Structure Template.xlsx
-----------------------------------------------

DESCRIPTION:
This document captures the fee structure ...

INSTRUCTIONS:
1. Download the attached sample file ...
...
8. Once complete, upload the filled Excel file using the upload button below.
```

## Good to know

- **No sample file?** Claude writes from the document name alone and adds a note saying so — check
  those items.
- **Several sheets in one Excel file** are described one by one.
- **Reference files** (examples, not templates) get "use this as a reference" wording, not "fill in".
- **Client contacts in the JSON are never copied** into the output. They only tell Claude who the
  reader is.
- "Mandatory" is not written into the description — the system already shows that.

## For developers

- `SKILL.md` — the instructions Claude follows: the JSON fields read, how each file type is
  analysed, output format, edge cases, and the quality checklist.
