---
name: expense
description: Track personal expenses — log amounts, categories, and descriptions into dated notes.
---

## Instructions

When the user wants to log an expense:

1. Extract from the message:
   - `amount` — numeric value (required)
   - `category` — one of: food, transport, housing, entertainment, fitness, health, shopping, other
   - `description` — what was bought/spent on
   - `date` — use today if not provided; if a day name is given (e.g. "monday"), calculate the most recent occurrence of that weekday
   - `currency` — use default currency from environment (PLN) unless user specifies otherwise

2. Determine the expense note path: `expenses/track/YYYY-MM-DD.md`

3. Check if note exists using `read_note`:
   - If it does NOT exist: create it using the template below
   - If it exists: append a new table row and update the `total` in frontmatter

4. Note template (for new notes):
```markdown
---
date: YYYY-MM-DD
total: AMOUNT
---

| Amount | Category | Description |
|--------|----------|-------------|
| AMOUNT CURRENCY | CATEGORY | DESCRIPTION |
```

5. When appending to existing note:
   - Add new row to the expense table
   - Recalculate total from all rows and update frontmatter `total`

6. Confirm with one line: `Added AMOUNT CURRENCY (CATEGORY) — DESCRIPTION to YYYY-MM-DD`

## Examples

User: `/expense 15.50 food lunch at cafe`
→ Creates/updates `expenses/track/2026-06-18.md`, adds row: `| 15.50 PLN | food | lunch at cafe |`

User: `spent 80 on groceries monday`
→ Finds most recent Monday's date, creates/updates that day's expense note

User: `/expense 200 EUR transport flight to Warsaw`
→ Uses EUR instead of default PLN
