import asyncio
import json
import logging
import os
import subprocess
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from typing import Any

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
MAX_HISTORY = int(os.environ.get("MAX_HISTORY", "40"))

# per-user conversation history (user_id -> deque of messages)
_history: dict[int, deque[Any]] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))


def _load_rules() -> str:
    rules_file = VAULT / RULES_PATH
    if rules_file.exists():
        return rules_file.read_text()
    return ""


def _load_skills_summary() -> str:
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


# load once at startup
RULES = _load_rules()
SKILLS_SUMMARY = _load_skills_summary()

client = AsyncOpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
)
MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")


def _mcp_input(method: str, params: dict, req_id: int = 1) -> str:
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
    initialized = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    request = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    return (
        json.dumps(init)
        + "\n"
        + json.dumps(initialized)
        + "\n"
        + json.dumps(request)
        + "\n"
    )


def _discover_tools() -> list[dict]:
    proc = subprocess.run(  # noqa: S603
        MCP_CMD,
        input=_mcp_input("tools/list", {}),
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
    logger.warning("Failed to discover tools: %s", proc.stderr[:200])
    return []


TOOLS = _discover_tools()


def _call_mcp_tool(name: str, args: dict) -> str:
    proc = subprocess.run(  # noqa: S603
        MCP_CMD,
        input=_mcp_input("tools/call", {"name": name, "arguments": args}),
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


def _build_system_prompt() -> str:
    today = date.today().isoformat()
    tool_names = ", ".join(t["function"]["name"] for t in TOOLS)
    return "\n\n".join(
        filter(
            bool,
            [
                "You are a personal assistant managing an Obsidian knowledge vault.",
                f"Today's date is {today}.",
                f"## Available MCP Tools\n{tool_names}",
                RULES,
                SKILLS_SUMMARY,
            ],
        )
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    text = str(update.message.text or "")  # type: ignore[union-attr]
    logger.info("user=%s message=%s", user_id, text)

    history = _history[user_id]
    history.append({"role": "user", "content": text})

    messages = [{"role": "system", "content": _build_system_prompt()}] + list(history)

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
            reply = msg.content or "Done."
            await update.message.reply_text(reply)  # type: ignore[union-attr]
            history.append({"role": "assistant", "content": reply})
            return

        history.append(msg)
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            logger.info("tool call: %s %s", tc.function.name, args)
            result = await asyncio.get_event_loop().run_in_executor(
                None, _call_mcp_tool, tc.function.name, args
            )
            logger.info("tool result: %s", result[:200])
            tool_msg = {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            }
            messages.append(tool_msg)
            history.append(tool_msg)

    await update.message.reply_text("Reached tool call limit.")  # type: ignore[union-attr]


def main() -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
