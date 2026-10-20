# Chat targets — limits, syntax, files (retrieved 2026-10-01)

`scripts/ts_chat.py` writes one message per saved target and never posts anywhere or handles a webhook URL. Posting a built Discord or Slack message is the separate, confirmed `post` command (`scripts/ts_post.py`): the webhook URL comes only from `DISCORD_WEBHOOK_URL` / `SLACK_WEBHOOK_URL`, is validated against the official hosts and is never printed or stored. Teams, Gmail and WhatsApp are never posted.
Re-verify a row against its source before changing a limit in `TARGETS`.

## Per-target facts and the cap we enforce

| Target | Documented fact | Cap enforced (unit, file) | Links | Source |
|---|---|---|---|---|
| Discord | `content` "up to 2000 characters" (create and edit message). Embeds have a separate 6000-character budget (unused). | **2000 `len()` characters** of `discord_<date>.md` (identical to the legacy renderer; Discord does not say whether it counts code points or UTF-16 units) | `[label](url)` | docs.discord.com/developers/resources/message |
| Slack | `text`: "for best results" ≤ 4,000 chars, truncated above 40,000; `chat.update` hard 4,000; `markdown_text` ≤ 12,000. Escape `&` `<` `>` as `&amp; &lt; &gt;`; no escape exists for `* _ ~`. "URLs with spaces will break". | **4000 UTF-16 units** of `chat_slack_<date>.txt` (the documented budget, not the 40,000 truncation point) | `<url\|label>`, `*bold*` | docs.slack.dev/reference/methods/chat.postMessage ; docs.slack.dev/messaging/formatting-message-text |
| Teams | "The message size limit is 28 KB. When the size exceeds 28 KB, you receive an error." (28 KB = 28672 bytes). Adaptive Card TextBlock supports a CommonMark **subset**: `**bold**`, `_italic_`, bullet/numbered lists, `[Title](url)`; not supported: headers, tables, images, "anything not in the table" (so no backslash escapes — we neutralise link syntax structurally instead). | **28000 bytes (UTF-8)** of the whole `chat_teams_<date>.json` card envelope (672-byte margin). The `.md` is the same text for pasting. | `[label](url)` in the TextBlock | learn.microsoft.com/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook ; learn.microsoft.com/adaptive-cards/authoring-cards/text-features |
| WhatsApp | Cloud API text `body` "Maximum 4096 characters"; `*bold*` `_italic_` `~strike~`; URLs must start `http(s)://`. No link-label syntax: a bare URL auto-links (the "no labels" part is from secondary sources). The consumer app accepts far longer text (~65,536, secondary sources); 4096 is chosen deliberately as the documented limit. | **4096 UTF-16 units** of `chat_whatsapp_<date>.txt` | raw URLs (`label url`) | developers.facebook.com/docs/whatsapp/cloud-api/messages/text-messages ; developers.facebook.com/docs/whatsapp/cloud-api/reference/messages/ |
| Gmail | No hard Gmail limit applies to a day's update. Gmail clips message HTML at ~102 KB (unofficial but widely observed: Litmus/Klaviyo). The suite's single limit is the HTML file, so the pasted message is never clipped. Subject: kept short and sensible (name truncated at 80 characters), no RFC 5322 78-char cap (that applies to the encoded header on the wire, which Gmail handles). | **100000 bytes (UTF-8)** of `chat_gmail_<date>.html` | `<a href>` in HTML; `label <url>` in the plain twin | RFC 5322 §2.1.1 (context only); litmus.com / klaviyo.com (clipping, secondary) |

Unverified, deliberately not relied on: Discord's `[t](<url>)` angle form (third-party blogs only → we percent-encode instead); whether Discord/Slack/Meta count code points or UTF-16 units → Slack/WhatsApp use UTF-16 units (never under-counts), Discord keeps `len()` (legacy behaviour).

## Files per target (`build` prints every path)

| Target | Files | Notes |
|---|---|---|
| discord | `discord_<date>.md` | legacy name and format |
| slack | `chat_slack_<date>.txt` | mrkdwn. **`<url\|label>` is NOT parsed when pasted into the Slack composer** — send it through your own webhook / API; it shows literally if pasted. |
| teams | `chat_teams_<date>.json` (Adaptive Card payload for your own Workflows webhook), `chat_teams_<date>.md` (same text, to paste) | Workflows webhook posts Adaptive Cards; plain `{"text": …}` is reported as delivered but not shown in some tenants, so the card envelope is used. Never ask for or store the webhook URL. |
| gmail | `chat_gmail_<date>.html`, `chat_gmail_<date>.txt` | HTML has `<meta charset="utf-8">` (open from disk, select all, paste into a Gmail compose). Rows carry their number literally in a `<p>` (no `<ol>`, so no "1. 1."). The `.txt` starts `Subject: …` then a blank line, then the plain body. |
| whatsapp | `chat_whatsapp_<date>.txt` | `*bold*` header, raw URLs |

Re-running `build` overwrites only its own files; removing a target never deletes its old files.

## Rendering contract

Row: `<n>. <label>: <summary> Ref <ref>, <ref> (<h>h)`; refs separated by `, ` (WhatsApp and Gmail-text: ` · `).

Degradation ladder when over the cap (last link first at each stage): (1) drop a Jira ticket's `Title (Status)` → (2) unembed the link to its bare label → (3) error naming the exact overflow (`… shorten the summaries by at least N characters|bytes`). Entries, links and hours are never dropped. `render_all` reports every failing target at once.

Link detail rung: only `kind: "ticket"` links carry `title`/`status` (`[EXM-1](url) Title (Status)`); other kinds render as the plain link.

## Safety rules (all targets)

- Only `http://` / `https://` URLs are linked; anything else (`javascript:`, `data:`, `mailto:`, scheme-less) renders as its label with a warning.
- URLs: characters of Unicode categories Cc, Cf (bidi overrides, zero-width), Zl, Zp, Zs (incl. space, NBSP) and `< >` are percent-encoded everywhere; `( )` also on Discord/Teams (so `…/Foo_(bar)` stays one link); `|` and `&`→`&amp;` on Slack; `html.escape` on the Gmail `href`. Other URLs are byte-identical.
- Untrusted text (summary, row label, link label, Jira title/status) is collapsed to ONE line (every whitespace run, incl. U+0085/U+2028/9, becomes a space) so it cannot forge a numbered row or a `[x]: url` reference definition; `[`/`]` become `(`/`)`; `@everyone` / `@here` / `@channel` / `<@id>` / `<!x>` / `<#id>` are defanged with a zero-width space. Applied identically on every target. Slack and Gmail additionally entity-escape (`& < >`); Teams uses no backslash escaping.
- Lone UTF-16 surrogates are replaced by U+FFFD (they cannot be encoded).
- Discord output equals the legacy `render_discord` for text/URLs that avoid the characters above (golden test `DiscordGoldenTests`).
