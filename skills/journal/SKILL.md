---
name: journal
description: Manage weekly journal notes — view todos, add tasks, mark tasks done, and append notes in Monday-based weekly files.
---

## Purpose

Use this skill when the user wants to work with weekly journal notes.

## Weekly note rule

There are no daily journal notes.

Weekly journal notes live in:

`journal/YYYY-MM-DD.md`

The filename must always be the Monday date of that week.

Example:
- If the week is June 15–21, 2026, the note is `journal/2026-06-15.md`

## Date anchor rules

- Always use the current date from the system context as the reference point
- Weeks start on Monday
- Monday is weekday 0, Tuesday 1, Wednesday 2, Thursday 3, Friday 4, Saturday 5, Sunday 6
- This week’s note date = today minus weekday offset
- Example:
  - Today: 2026-06-18
  - Weekday: Thursday = 3
  - Monday: 2026-06-15
  - Note: `journal/2026-06-15.md`

## Supported note format

Each weekly note should use this structure:

```markdown
***
date: YYYY-MM-DD
week: WW
***

## TODO
- [ ] item

## Done
- [x] item

## Notes
```

Rules:
- Keep the section headings exactly as `TODO`, `Done`, and `Notes`
- Preserve existing content order
- Do not remove completed or unfinished tasks unless explicitly asked

## Week resolution rules

Resolve the target week before acting:

- “this week” → current week Monday
- “last week” → current week Monday minus 7 days
- “next week” → current week Monday plus 7 days, only if the user explicitly asks for next week
- Exact date → use the Monday of that date’s week
- A weekday-only phrase like “on Tuesday” should normally refer to this week unless the user clearly means another week
- If the intended week is unclear, ask one short clarifying question

## File existence rules

- First calculate the correct Monday date
- Then check whether that weekly note exists
- If it does not exist and the user wants to add or change something, create it using the standard weekly template
- If it does not exist and the user only wants to view content, say there is no note for that week
- Do not silently switch to another week
- Only inspect nearby or recent weekly notes if the user asks to find something across weeks

## Operations

### View todos

When the user asks for current-week todos:

1. Resolve this week’s Monday date
2. Read that weekly note
3. Extract only unchecked items from the `TODO` section
4. Return them as plain text bullets
5. Do not show checkboxes, markdown, or file paths

If none exist, say so simply.

### Add todo

When the user asks to add a todo:

1. Resolve the correct week
2. Find or create that weekly note
3. Append a new unchecked item under `TODO`
4. Keep the original wording unless a cleanup is obviously helpful

Format to append:

`- [ ] task`

### Mark todo done

When the user asks to mark a todo done:

1. Resolve the correct week
2. Read the note
3. Find the matching unchecked todo
4. Change it from unchecked to checked
5. Move it to the `Done` section if your tools support that cleanly; otherwise mark it checked in place
6. If multiple todos match, ask one short clarifying question
7. If no matching todo exists, say so simply

Matching rules:
- Match exact text first
- If no exact match exists, allow a close match only when there is one obvious candidate
- If more than one candidate is plausible, ask

### View todos from another week

When the user asks for another week’s todos:

1. Resolve that week’s Monday date
2. Read the weekly note
3. Extract unchecked items from `TODO`
4. Return them as plain bullets

### Carried-over todos

When the user asks what did not get done last week or what carried over:

1. Resolve this week’s Monday date
2. Calculate last week’s Monday date = this Monday minus 7 days
3. Read last week’s note
4. Extract unchecked items from last week’s `TODO` section
5. Return them as plain bullets
6. Do not automatically copy them into this week unless the user asks

### Add note or thought

When the user wants to add a note, reflection, or thought:

1. Resolve the target week
2. Find or create the weekly note
3. Append the content under `Notes`
4. Preserve existing notes content

## Response rules

- Always respond in plain text
- Never show markdown syntax unless the user asks for the exact note
- Never show file paths unless the user asks
- Todos should appear as simple bullets or numbered items
- If no todos are found, say so briefly
- Confirmation replies should be short

## Safe behavior

- Do not silently use the most recent note as a fallback for the wrong week
- Do not guess a week when the user’s request is ambiguous
- Do not delete tasks while completing them
- Do not rewrite the whole note when a small patch is enough
- Preserve unrelated content

## Examples

User: `what are my todos this week`
Result:
- resolve this week’s Monday
- read that weekly note
- return only unfinished todo items as plain bullets

User: `add todo buy dog food`
Result:
- resolve this week
- create weekly note if missing
- append `- [ ] buy dog food` under `TODO`

User: `mark buy dog food done`
Result:
- resolve this week
- find matching todo
- mark it done
- ask only if multiple matches exist

User: `what carried over from last week`
Result:
- read last week’s note
- return unfinished todo items as plain bullets

User: `add note felt tired after tennis`
Result:
- append the sentence under `Notes` in the correct weekly note