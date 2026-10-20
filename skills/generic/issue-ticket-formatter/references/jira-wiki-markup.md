# Jira old wiki markup (only if the user asks for it)

Modern Jira (cloud, new editor) accepts pasted GitHub-flavoured Markdown and converts it, so
the default Markdown output usually works as-is. Convert to wiki markup ONLY when the user
says their Jira uses the old markup / the Markdown isn't rendering.

Mapping:

| Markdown | Jira wiki markup |
|---|---|
| `# H1` | `h1. H1` |
| `## H2` | `h2. H2` |
| `**bold**` | `*bold*` |
| `*italic*` | `_italic_` |
| `` `code` `` | `{{code}}` (inline monospace) |
| ```` ```python … ``` ```` | `{code:python} … {code}` |
| `- item` | `* item` |
| `1. item` | `# item` |
| `- [ ] task` | `(x) task` or a checkbox macro — Jira has no native MD task list; use `(/)` done / `(x)` not-done, or keep `- [ ]` if the instance supports it |
| `[text](url)` | `[text|url]` |
| Markdown table | `||H1||H2||` header row, then `|a|b|` rows |
| `> quote` | `{quote} … {quote}` |
| `⚠️` callout block | `{panel:title=Warning|borderColor=#c00}…{panel}` |

Keep the same content and section order; only the syntax changes.
