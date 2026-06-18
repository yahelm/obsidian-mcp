import asyncio
import json
import os
import subprocess
from datetime import date
from pathlib import Path

import frontmatter
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

VAULT = Path(os.environ.get("VAULT_PATH", "/home/opc/vault-work"))
RULES_PATH = "_system/rules.md"
SKILLS_DIR = Path(os.environ.get("SKILLS_PATH", "/var/app/skills"))
MCP_CMD = ["obsidian-mcp"]


def _load_rules() -> str:
    rules_file = VAULT / RULES_PATH
    if rules_file.exists():
        return rules_file.read_text()
    return ""


def _load_skills_summary() -> str:
    """Load skill names + descriptions only for system prompt discovery."""
    if not SKILLS_DIR.exists():
        return ""
    lines = []
    for skill_file in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        post = frontmatter.loads(skill_file.read_text())
        name = post.metadata.get("name", skill_file.parent.name)
        description = post.metadata.get("description", "")
        lines.append(f"- {name}: {description}")
    if not lines:
        return ""
    header = "## Available Skills\nUse read_skill(name) for full instructions."
    return header + "\n" + "\n".join(lines)


SKILLS_SUMMARY = _load_skills_summary()


client = AsyncOpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
)
MODEL = os.environ.get("LLM_MODEL", "gemini-2.0-flash")


def _get_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "create_note",
                "description": "Create or overwrite a note",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_note",
                "description": "Read a note by relative path",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "edit_note",
                "description": "Append content to existing note",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_notes",
                "description": "List notes in vault or subfolder",
                "parameters": {
                    "type": "object",
                    "properties": {"folder": {"type": "string"}},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_notes",
                "description": "Search note contents for a string",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_daily_note",
                "description": "Get or create today's daily note",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_todos",
                "description": "Find all incomplete todos in vault or folder",
                "parameters": {
                    "type": "object",
                    "properties": {"folder": {"type": "string"}},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "complete_todo",
                "description": "Mark a todo as complete",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "todo_text": {"type": "string"},
                    },
                    "required": ["path", "todo_text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_with_snippets",
                "description": "Search vault and return matching lines with context",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_backlinks",
                "description": "Find all notes that link to this note",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_skills",
                "description": "List available skills with names and descriptions",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_skill",
                "description": "Load full instructions for a skill by name",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        },
    ]


def _call_mcp_tool(name: str, args: dict) -> str:
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }
    init = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "bot", "version": "1.0"},
        },
    }
    proc = subprocess.run(  # noqa: S603
        MCP_CMD,
        input=json.dumps(init) + "\n" + json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        timeout=30,
    )
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
            if msg.get("id") == 1:
                result = msg.get("result", {})
                content = result.get("content", [])
                return "\n".join(
                    c.get("text", "") for c in content if c.get("type") == "text"
                )
        except json.JSONDecodeError:
            continue
    return f"Tool error: {proc.stderr[:200]}"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = str(update.message.text or "")  # type: ignore[union-attr]
    rules = _load_rules()
    today = date.today().isoformat()
    system_content = "\n\n".join(
        filter(
            bool,
            [
                "You are a personal assistant managing an Obsidian knowledge vault.",
                f"Today's date is {today}.",
                rules,
                SKILLS_SUMMARY,
            ],
        )
    )
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": text},
    ]

    tools = _get_tools()
    for _ in range(10):
        response = await client.chat.completions.create(  # type: ignore[call-overload]
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            await update.message.reply_text(msg.content or "Done.")  # type: ignore[union-attr]
            return

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = await asyncio.get_event_loop().run_in_executor(
                None, _call_mcp_tool, tc.function.name, args
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

    await update.message.reply_text("Reached tool call limit.")  # type: ignore[union-attr]


def main() -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
