---
name: journal
description: Manage weekly journal notes — view todos, add tasks, mark done, add notes. Weekly notes live in journal/ folder named by Monday's date (YYYY-MM-DD.md).
---

## Instructions

Weekly notes are stored in `journal/` named by the Monday of that week (e.g. `journal/2026-06-15.md`).

To find the current week's note: calculate the most recent Monday from today's date.

### Note format

```markdown
---
date: YYYY-MM-DD
week: WW
---

## TODO
- [ ] item

## Done
- [x] item

## Notes

```

### Operations

**View todos:**
1. Calculate current Monday's date
2. Read `journal/YYYY-MM-DD.md`
3. Extract all `- [ ]` lines from the TODO section

**Add todo:**
1. Find current week's note (create if missing using template above)
2. Append `- [ ] task` to the TODO section using `patch_content_by_anchor` with heading `TODO` and action `append`

**Mark todo done:**
1. Read current week's note
2. Use `complete_todo` tool with the exact todo text

**Add note/thought:**
1. Find current week's note
2. Append to Notes section using `patch_content_by_anchor` with heading `Notes` and action `append`

**Create new weekly note:**
- Path: `journal/YYYY-MM-DD.md` where date is the Monday of that week
- Use the template above, fill in `date` and `week` frontmatter

### Finding Monday's date

Today is provided in the system prompt. Calculate: `today - (today.weekday())` days to get Monday.
Example: if today is Wednesday June 18 2026 (weekday=2), Monday = June 18 - 2 = June 16 2026.

### Carried-over todos

When user asks "what didn't I finish last week" or "what carried over":
1. Calculate last Monday = this Monday - 7 days
2. Read `journal/LAST-MONDAY.md`
3. Find all `- [ ]` lines (unchecked) in TODO section — these were not completed
4. Read `journal/THIS-MONDAY.md` — check which of those items appear as `- [x]` (already moved and done) or `- [ ]` (carried over and still open)
5. Report: items that are unchecked in last week's note and also present (checked or unchecked) in this week's note = carried over; items only in last week unchecked = forgotten/dropped
