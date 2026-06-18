import asyncio
import json
import logging
import os
import subprocess
from datetime import date
from pathlib import Path

import frontmatter
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

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


def _discover_tools() -> list[dict]:
    """Query MCP server for available tools at startup."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
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
                tools = msg.get("result", {}).get("tools", [])
                return [
                    {
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parameters": t.get(
                                "inputSchema", {"type": "object", "properties": {}}
                            ),
                        },
                    }
                    for t in tools
                ]
        except json.JSONDecodeError:
            continue
    logger.warning("Failed to discover tools from MCP server: %s", proc.stderr[:200])
    return []


TOOLS = _discover_tools()


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
    logger.info("message: %s", text)
    rules = _load_rules()
    today = date.today().isoformat()
    tool_names = ", ".join(t["function"]["name"] for t in TOOLS)
    system_content = "\n\n".join(
        filter(
            bool,
            [
                "You are a personal assistant managing an Obsidian knowledge vault.",
                f"Today's date is {today}.",
                f"## Available MCP Tools\n{tool_names}",
                rules,
                SKILLS_SUMMARY,
            ],
        )
    )
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": text},
    ]

    for _ in range(10):
        response = await client.chat.completions.create(  # type: ignore[call-overload]
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            await update.message.reply_text(msg.content or "Done.")  # type: ignore[union-attr]
            return

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            logger.info("tool call: %s %s", tc.function.name, args)
            result = await asyncio.get_event_loop().run_in_executor(
                None, _call_mcp_tool, tc.function.name, args
            )
            logger.info("tool result: %s", result[:200])
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
