---
name: doc-request-helper
description: >
  Generates professional descriptions and upload instructions for each item in a Unity Edu
  Project Document Request. Trigger whenever the user shares JSON of a Document Request
  (or mentions "document request", "DOC-REQ", "upload instructions", "document description")
  and wants description/instructions for the client upload portal. Also trigger on
  "generate instructions for this request", "write upload guidance", "analyze this request
  and sample files", or when a JSON blob with `doctype: "Project Document Request"` is pasted
  alongside sample files — even without an explicit ask. Output: a .txt file with description
  + numbered instructions per item, ready to copy-paste.
---

# Document Request — Description & Instruction Generator

Generates polished, client-facing **descriptions** and **upload instructions** for every item
in a Unity Edu Project Document Request. Output is a plain `.txt` file the team can copy-paste
directly into the system's description and instruction fields.

---

## Step 1 — Parse the JSON

Extract the following from the provided JSON:

| Field | Source Path |
|-------|------------|
| Request ID | `name` |
| Request Title | `request_title` |
| Project | `project` |
| Client | `client_name` |
| Template Type | `template` |
| Document Items | `request_documents[]` — each has `document_name`, `is_mandatory`, `sample_file` |
| Client Contacts | `client_contacts[]` — for context on who will receive this |

Build a working list of all items from `request_documents`. Each item will get its own description + instructions block.

---

## Step 2 — Analyze Each Sample File

For every item in `request_documents` that has a `sample_file`, read the corresponding uploaded file to understand its structure:

**For Excel files (.xlsx, .xls, .csv):**
- Read all sheet names
- Read all column headers
- Read all row labels / pre-filled values
- Note which columns are empty (to be filled by the client)
- Note the total number of entries / rows expected

**For PDF files:**
- Extract text to understand what sections or fields need filling
- Note if it's a form with blanks vs. a reference document

**For Word documents (.docx):**
- Read headings and structure
- Identify placeholder text or blank fields

**For image files:**
- Note that this is a visual reference / sample format

If the sample file is not uploaded but a path is mentioned in JSON (`sample_file` field), note it and work with whatever context is available from the document name and template type.

---

## Step 3 — Generate Description

Write a **description** for each document item. The description should:

- Be 2–4 sentences long
- Explain **what** the document is and **why** it's needed
- List the key items / sections the client needs to provide (derived from the sample file analysis)
- Mention the file format expected (Excel, PDF, etc.)
- If the item is mandatory, do NOT mention "mandatory" in the description — that's handled by the system's `is_mandatory` flag

**Tone:** Professional, clear, non-technical. Written for a school admin or operations head — not a developer.

**Example:**
```
This document captures the fee structure details for all student categories across the academic year. The sample file contains columns for Fee Category, Amount, Frequency, Applicable Classes, and Due Dates. Please fill in all rows with your school's actual fee data for the upcoming session.
```

---

## Step 4 — Generate Instructions

Write **numbered instructions** for each document item. Instructions should:

- Start with downloading/reviewing the sample file
- Walk through what to fill, column by column or section by section
- Mention any placeholders or dynamic variables if applicable (e.g., `{student_name}`, `{amount}`)
- Warn against changing headers, column names, or file structure
- End with the upload step
- Be 4–8 points typically — enough to be clear, not so many that it feels overwhelming

**Tone:** Friendly but precise. Like a helpful colleague giving step-by-step guidance.

**Example:**
```
1. Download the attached sample file ("Fee Structure Template.xlsx").
2. In the "Fee Category" column, enter each type of fee your school charges (e.g., Tuition, Transport, Lab Fee, Activity Fee).
3. In the "Amount" column, enter the fee amount in INR for each category.
4. In the "Frequency" column, specify how often this fee is charged — Monthly, Quarterly, Annually, or One-Time.
5. In the "Applicable Classes" column, list the classes/grades this fee applies to (e.g., "Grade 1–5" or "All").
6. In the "Due Date" column, enter the expected payment due date for each fee.
7. Do not rename or reorder the columns — the system uses the exact column headers to import your data.
8. Once complete, upload the filled Excel file using the upload button below.
```

---

## Step 5 — Assemble & Output

Combine all items into a single `.txt` file with this structure:

```
===============================================
DOCUMENT REQUEST: [Request ID]
PROJECT: [Project Name]
CLIENT: [Client Name]
TEMPLATE: [Template Type]
===============================================

-----------------------------------------------
ITEM 1: [Document Name]
Mandatory: Yes / No
Sample File: [filename]
-----------------------------------------------

DESCRIPTION:
[Generated description text]

INSTRUCTIONS:
1. [First instruction]
2. [Second instruction]
...

-----------------------------------------------
ITEM 2: [Document Name]
...
-----------------------------------------------
```

Repeat for every item in `request_documents`.

---

## Step 6 — Save & Present

1. Save the file as `[RequestID]_instructions.txt` in the current working directory, or in the
   folder the user asked for
2. If the environment has a tool for sharing files with the user, use it; otherwise give the full
   path
3. Briefly confirm what was generated — mention the number of items and the client name

---

## Edge Cases

- **No sample file uploaded but path exists in JSON:** Generate description and instructions based on the document name and template type alone. Add a note: _"(Instructions inferred from document name — review and adjust if the actual sample file differs.)"_
- **Multiple sheets in an Excel file:** Describe each sheet separately within the same item's description and instructions.
- **Sample file is a reference/example (not a template to fill):** Adjust instructions to say "Use this as a reference format" rather than "Fill in this file."
- **JSON has only one document item:** Still use the full output format — don't skip the structure.
- **Client contacts exist:** Do not include contact details in the output. They are for context only (to understand the audience).

---

## Quality Checklist

Before outputting, verify each item's description and instructions against:

- [ ] Description explains the purpose clearly to a non-technical person
- [ ] Instructions reference the actual column names / sections from the sample file
- [ ] No developer jargon (no "DocType", "API", "webhook", "field type")
- [ ] File format expectation is stated
- [ ] "Do not change headers/structure" warning is included where applicable
- [ ] Placeholder variables are listed if the document involves templates (emails, SMS, letters)
- [ ] Instructions end with a clear upload step
