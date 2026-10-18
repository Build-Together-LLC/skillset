# Writing style for demo guides

- Audience: a capable person who has the product but has never set this up. Never assume they know the vendor's words.
- One action per step. Imperative verbs ("Click Save"). Put the thing to click in **bold**.
- After every command or click say **What you should see** (use `expect`). Give the exact text or status code.
- Commands in a code block, comments start with `#`. Replace secrets with obvious placeholders or example values.
- Tables for fields, options, statuses, troubleshooting. Prose for explanations of *why*.
- Every screenshot has numbered badges and a caption that says what the numbers mean, then a table or list that uses
  the same numbers.
- Give both the **local** and the **server/VPS** path when they differ, and say which to pick.
- Troubleshooting is symptom -> likely cause -> fix, with the command that proves the fix.
- Close with a command cheat-sheet and a links table. Every URL is a clickable hyperlink (the library does this for you).
- Verify every link with `curl -s -o /dev/null -w '%{http_code}' -L <url>` before shipping. Fix or drop anything that is not 200.
- Be honest about limits ("tested on version X", "not tested with Y").
