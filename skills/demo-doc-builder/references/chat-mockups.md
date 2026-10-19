# Chat and phone mockups (WhatsApp, SMS, in-app chat)

A screenshot of a real phone is rarely possible and always carries a real number. Draw the conversation instead, from the
product's own strings, and say on the cover that the screens are rebuilt.

1. **Get the real text.** Call the product's own message builders with a sender that records instead of sending
   (a small script run in the app's console: `SENT.append({"type": ..., "body": ..., "data": ...})`). Capture every message the
   flow produces: question, buttons, list rows, confirmation, error and apology text. Never type them from memory.
2. **Write the transcript JSON** for `scripts/chat_mock.py` (see its header): `in` is the business, `out` is the user,
   `buttons` are quick replies, `choose` is the list button, `sheet` is the list that opens over the chat.
3. **Swap real addresses for example ones** with `"replace": [real, example]`. Check bubbles for phone numbers and names.
4. **Size**: height 600 to 650 keeps the empty space at the top small. When a `sheet` is open, use 640 or more so the message above it stays visible.
5. In a guide put 3 to 4 phones in one row with `figrow` (1.4 to 1.9 in each); in a deck use `quad` (2.2 to 2.4 in each). Caption each with what the
   user does and what the product answers.
6. Table the logic next to the pictures (condition -> result), because a picture does not show the rules (time limits, who is refused, what is hidden).
