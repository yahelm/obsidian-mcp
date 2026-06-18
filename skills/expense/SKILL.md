---
name: expense
description: Track personal expenses by logging amounts, categories, descriptions, and currency into dated daily notes.
---

## Purpose

Use this skill when the user wants to record a personal expense in the vault.

## Supported categories

- food
- transport
- housing
- entertainment
- fitness
- health
- shopping
- other

## Extraction rules

From the user message, extract:

- `amount` — numeric value, required
- `category` — one supported category
- `description` — short human-readable description of the expense
- `date` — if omitted, use today in the user’s local timezone
- `currency` — use user-specified currency if present; otherwise default to PLN

## Date rules

- If the user gives an exact date, use it
- If the user gives a weekday like “monday”, use the most recent occurrence of that weekday in the user’s local timezone
- Do not use a future date unless the user explicitly says so
- If the date is ambiguous, ask one short clarifying question

## Category mapping rules

Map common phrases to categories when obvious:

- groceries, lunch, dinner, cafe, restaurant → `food`
- uber, taxi, bus, train, fuel, parking → `transport`
- rent, bills, utilities, internet → `housing`
- cinema, games, concert, streaming → `entertainment`
- gym, tennis, supplements → `fitness`
- doctor, pharmacy, dentist, medicine → `health`
- clothes, electronics, Amazon, Allegro → `shopping`

If the category is still unclear, use `other`.

## Note path

Use this path:

`expenses/track/YYYY-MM-DD.md`

## Note format

Each expense note must use this structure:

```markdown
***
date: YYYY-MM-DD
total: 0
currency: PLN
***

| Amount | Category | Description |
|--------|----------|-------------|
| 0.00 PLN | food | example |
```

Rules:
- Always include currency in the `Amount` column
- Keep exactly one expense table per daily note
- Preserve existing rows when updating

## Create behavior

If the note does not exist:

1. Create the note at `expenses/track/YYYY-MM-DD.md`
2. Add frontmatter with:
   - `date`
   - `total`
   - `currency`
3. Insert the expense table
4. Add the first expense row
5. Set `total` equal to the new row amount

## Update behavior

If the note exists:

1. Read the existing note
2. Find the expense table
3. Append one new row
4. Recalculate the total from all rows
5. Update frontmatter `total`

## Currency rules

- If the note already exists and uses the same currency as the new expense, update `total` normally
- If the new expense uses a different currency than the existing note currency, do not merge it silently
- In that case, ask one short question:
  - “That daily note is in PLN, but this expense is in EUR. Add it anyway and keep mixed currencies, or create a separate note?”
- Never convert currencies automatically unless the user explicitly asks

## Validation rules

Before writing:
- `amount` must be present and numeric
- `category` must be one of the supported categories
- `description` must not be empty; if missing, infer a short description from the message
- `date` must resolve to a valid date

If the existing note is malformed:
- If frontmatter is missing, repair it
- If the expense table is missing, recreate it without deleting valid content
- If the table format is broken, preserve the original content and append a corrected table below
- Do not delete user data

## Read/write behavior

- Prefer updating the existing daily note instead of creating duplicates
- Preserve unrelated content already present in the note
- Do not reorder old entries unless needed to repair the table
- Keep formatting consistent with vault rules

## Confirmation format

Reply with exactly one short line:

`Added AMOUNT CURRENCY (CATEGORY) — DESCRIPTION to YYYY-MM-DD`

## Examples

User: `/expense 15.50 food lunch at cafe`
Result:
- create or update `expenses/track/2026-06-18.md`
- append: `| 15.50 PLN | food | lunch at cafe |`

User: `spent 80 on groceries monday`
Result:
- resolve the most recent Monday
- map groceries → `food`
- create or update that daily note

User: `/expense 200 EUR transport flight to Warsaw`
Result:
- use EUR
- if the note already uses PLN, ask before mixing currencies