import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import frontmatter
import yaml
from mcp.server.fastmcp import FastMCP

VAULT = Path(os.environ.get("VAULT_PATH", "/home/opc/vault-work"))
SKILLS_DIR = Path(os.environ.get("SKILLS_PATH", "/var/app/skills"))
GIT = shutil.which("git") or "git"

mcp = FastMCP("obsidian")


# --- helpers ---


def _git_push(msg: str) -> None:
    subprocess.run([GIT, "add", "-A"], cwd=VAULT, check=True)  # noqa: S603
    result = subprocess.run(  # noqa: S603
        [GIT, "commit", "-m", f"bot: {msg}"], cwd=VAULT, capture_output=True
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git commit failed: {result.stderr.decode()}")
    subprocess.run([GIT, "push"], cwd=VAULT, check=True)  # noqa: S603


def _extract_links(text: str) -> list[str]:
    return re.findall(r"\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]", text)


def _extract_tags(text: str) -> list[str]:
    fm = frontmatter.loads(text)
    tags: list[str] = []
    if "tags" in fm.metadata:
        t = fm.metadata["tags"]
        tags = [str(x) for x in t] if isinstance(t, list) else [str(t)]
    inline = re.findall(r"(?<!\S)#([\w/-]+)", fm.content)
    return list(set(tags + inline))


def _all_md_files() -> list[Path]:
    return [p for p in VAULT.rglob("*.md") if ".git" not in p.parts]


# --- notes ---


@mcp.tool()
def create_note(path: str, content: str) -> str:
    """Create or overwrite a note. path relative to vault root e.g. 'folder/note.md'"""
    target = VAULT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    _git_push(f"create {path}")
    return f"Created {path}"


@mcp.tool()
def read_note(path: str) -> str:
    """Read a note by relative path"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    return target.read_text()


@mcp.tool()
def edit_note(path: str, content: str) -> str:
    """Append content to existing note"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    with target.open("a") as f:
        f.write(f"\n{content}")
    _git_push(f"edit {path}")
    return f"Appended to {path}"


@mcp.tool()
def delete_note(path: str) -> str:
    """Delete a note"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    target.unlink()
    _git_push(f"delete {path}")
    return f"Deleted {path}"


@mcp.tool()
def move_note(old_path: str, new_path: str) -> str:
    """Move or rename a note"""
    src = VAULT / old_path
    dst = VAULT / new_path
    if not src.exists():
        return f"Not found: {old_path}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)
    _git_push(f"move {old_path} -> {new_path}")
    return f"Moved {old_path} to {new_path}"


@mcp.tool()
def combine_notes(
    paths: list[str], output_path: str, separator: str = "\n\n---\n\n"
) -> str:
    """Merge multiple notes into one"""
    parts = []
    for p in paths:
        target = VAULT / p
        if target.exists():
            parts.append(f"# {target.stem}\n\n{target.read_text()}")
    if not parts:
        return "No notes found"
    combined = separator.join(parts)
    out = VAULT / output_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(combined)
    _git_push(f"combine -> {output_path}")
    return f"Combined {len(parts)} notes into {output_path}"


@mcp.tool()
def list_notes(folder: str = "") -> str:
    """List notes in vault or subfolder"""
    base = VAULT / folder if folder else VAULT
    files = [
        str(p.relative_to(VAULT)) for p in base.rglob("*.md") if ".git" not in p.parts
    ]
    return "\n".join(sorted(files))


@mcp.tool()
def get_recent_notes(days: int = 7) -> str:
    """List notes modified in the last N days"""
    import time

    cutoff = time.time() - days * 86400
    results = []
    for f in _all_md_files():
        if f.stat().st_mtime >= cutoff:
            results.append(str(f.relative_to(VAULT)))
    return "\n".join(sorted(results)) if results else "No recent notes"


# --- search ---


@mcp.tool()
def search_notes(query: str) -> str:
    """Search note contents for a string"""
    results = []
    for f in _all_md_files():
        text = f.read_text(errors="ignore")
        if query.lower() in text.lower():
            results.append(str(f.relative_to(VAULT)))
    return "\n".join(results) if results else "No matches"


@mcp.tool()
def search_by_tag(tag: str) -> str:
    """Find notes containing a specific tag"""
    results = []
    for f in _all_md_files():
        tags = _extract_tags(f.read_text(errors="ignore"))
        if tag.lower() in [t.lower() for t in tags]:
            results.append(str(f.relative_to(VAULT)))
    return "\n".join(results) if results else "No matches"


# --- relations ---


@mcp.tool()
def get_links(path: str) -> str:
    """Get all [[wikilinks]] in a note"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    links = _extract_links(target.read_text())
    return "\n".join(links) if links else "No links"


@mcp.tool()
def get_backlinks(path: str) -> str:
    """Find all notes that link to this note"""
    stem = Path(path).stem
    results = []
    for f in _all_md_files():
        if str(f.relative_to(VAULT)) == path:
            continue
        links = _extract_links(f.read_text(errors="ignore"))
        if stem in [Path(link).stem for link in links]:
            results.append(str(f.relative_to(VAULT)))
    return "\n".join(results) if results else "No backlinks"


@mcp.tool()
def get_vault_graph() -> str:
    """Get full link graph of vault as adjacency list"""
    graph = {}
    for f in _all_md_files():
        key = str(f.relative_to(VAULT))
        links = _extract_links(f.read_text(errors="ignore"))
        graph[key] = links
    lines = [f"{k} -> {', '.join(v)}" if v else k for k, v in sorted(graph.items())]
    return "\n".join(lines)


# --- frontmatter / tags ---


@mcp.tool()
def get_tags(path: str) -> str:
    """Get all tags from a note (frontmatter + inline)"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    tags = _extract_tags(target.read_text())
    return "\n".join(tags) if tags else "No tags"


@mcp.tool()
def update_frontmatter(path: str, key: str, value: str) -> str:
    """Add or update a frontmatter key in a note"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    post = frontmatter.loads(target.read_text())
    post.metadata[key] = value
    target.write_text(frontmatter.dumps(post))
    _git_push(f"frontmatter {path}")
    return f"Set {key}={value} in {path}"


# --- daily note ---


@mcp.tool()
def get_daily_note() -> str:
    """Get or create today's daily note"""
    today = date.today().isoformat()
    path = VAULT / "Daily" / f"{today}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# {today}\n\n")
        _git_push(f"daily {today}")
    return path.read_text()


# --- todos ---


@mcp.tool()
def get_todos(folder: str = "") -> str:
    """Find all incomplete todos (- [ ]) in vault or folder"""
    base = VAULT / folder if folder else VAULT
    results = []
    for f in base.rglob("*.md"):
        if ".git" in f.parts:
            continue
        for line in f.read_text(errors="ignore").splitlines():
            if "- [ ]" in line:
                results.append(f"{f.relative_to(VAULT)}: {line.strip()}")
    return "\n".join(results) if results else "No open todos"


@mcp.tool()
def complete_todo(path: str, todo_text: str) -> str:
    """Mark a todo as complete by matching text"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    text = target.read_text()
    new_text = text.replace(f"- [ ] {todo_text}", f"- [x] {todo_text}", 1)
    if new_text == text:
        return f"Todo not found: {todo_text}"
    target.write_text(new_text)
    _git_push(f"complete todo in {path}")
    return f"Completed: {todo_text}"


# --- structure ---


@mcp.tool()
def get_note_outline(path: str) -> str:
    """Return heading structure (TOC) with line numbers for a note"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    outline = []
    for i, line in enumerate(target.read_text().splitlines(), 1):
        m = re.match(r"^(#{1,6})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            title = m.group(2)
            indent = "  " * (level - 1)
            outline.append(f"L{i}: {indent}{title}")
    return "\n".join(outline) if outline else "No headings"


@mcp.tool()
def find_orphaned_notes() -> str:
    """Find notes with no inbound links (not linked from any other note)"""
    all_files = _all_md_files()
    linked = set()
    for f in all_files:
        for link in _extract_links(f.read_text(errors="ignore")):
            linked.add(Path(link).stem)
    orphans = [str(f.relative_to(VAULT)) for f in all_files if f.stem not in linked]
    return "\n".join(sorted(orphans)) if orphans else "No orphans"


@mcp.tool()
def find_broken_links() -> str:
    """Find all broken [[wikilinks]] across entire vault"""
    all_files = _all_md_files()
    all_stems = {f.stem for f in all_files}
    broken = []
    for f in all_files:
        for link in _extract_links(f.read_text(errors="ignore")):
            if Path(link).stem not in all_stems:
                broken.append(f"{f.relative_to(VAULT)}: [[{link}]]")
    return "\n".join(broken) if broken else "No broken links"


@mcp.tool()
def patch_content_by_anchor(path: str, heading: str, action: str, content: str) -> str:
    """Edit a specific section of a note by heading.

    action: append | prepend | replace
    """
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    lines = target.read_text().splitlines(keepends=True)
    heading_pattern = re.compile(r"^#{1,6}\s+" + re.escape(heading) + r"\s*$")
    start = None
    for i, line in enumerate(lines):
        if heading_pattern.match(line):
            start = i
            break
    if start is None:
        return f"Heading not found: {heading}"
    # find end of section (next same-or-higher heading or EOF)
    m0 = re.match(r"^(#+)", lines[start])
    level = len(m0.group(1)) if m0 else 1
    end = len(lines)
    for i in range(start + 1, len(lines)):
        m = re.match(r"^(#+)\s", lines[i])
        if m and len(m.group(1)) <= level:
            end = i
            break
    section_lines = lines[start + 1 : end]
    new_content = content.rstrip("\n") + "\n"
    if action == "replace":
        new_section = [new_content]
    elif action == "prepend":
        new_section = [new_content] + section_lines
    elif action == "append":
        new_section = section_lines + [new_content]
    else:
        return f"Unknown action: {action}. Use append | prepend | replace"
    result = lines[: start + 1] + new_section + lines[end:]
    target.write_text("".join(result))
    _git_push(f"patch {path} [{heading}]")
    return f"Patched section '{heading}' in {path}"


# --- advanced search ---


@mcp.tool()
def search_with_snippets(query: str, context_lines: int = 2) -> str:
    """Search vault and return matching lines with surrounding context"""
    results = []
    for f in _all_md_files():
        lines = f.read_text(errors="ignore").splitlines()
        for i, line in enumerate(lines):
            if query.lower() in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                snippet = "\n".join(lines[start:end])
                results.append(f"### {f.relative_to(VAULT)} (L{i + 1})\n{snippet}")
    return "\n\n".join(results) if results else "No matches"


@mcp.tool()
def search_and_replace(
    query: str, replacement: str, folder: str = "", dry_run: bool = True
) -> str:
    """Search and replace text across vault or folder.

    dry_run=True by default — shows changes without applying.
    """
    if not query:
        return "Error: query cannot be empty"
    base = VAULT / folder if folder else VAULT
    files = [p for p in base.rglob("*.md") if ".git" not in p.parts]
    matches = []
    for f in files:
        text = f.read_text(errors="ignore")
        if query in text:
            count = text.count(query)
            matches.append((f, text, count))
    if not matches:
        return "No matches"
    summary = "\n".join(
        f"{f.relative_to(VAULT)}: {c} occurrence(s)" for f, _, c in matches
    )
    if dry_run:
        return f"DRY RUN — would replace in:\n{summary}\n\nCall again with dry_run=False to apply."  # noqa: E501
    for f, text, _ in matches:
        f.write_text(text.replace(query, replacement))
    _git_push(f"replace '{query}' -> '{replacement}'")
    return f"Replaced in:\n{summary}"


# --- metadata ---


@mcp.tool()
def get_note_metadata(path: str) -> str:
    """Return only frontmatter metadata without note body (token-efficient)"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    post = frontmatter.loads(target.read_text())
    if not post.metadata:
        return "No frontmatter"
    return yaml.dump(post.metadata, default_flow_style=False).strip()


@mcp.tool()
def patch_frontmatter_properties(
    path: str, updates: dict, delete_keys: list[str] | None = None
) -> str:
    """Bulk update frontmatter: merge updates dict, delete listed keys"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"
    post = frontmatter.loads(target.read_text())
    post.metadata.update(updates)
    for key in delete_keys or []:
        post.metadata.pop(key, None)
    target.write_text(frontmatter.dumps(post))
    _git_push(f"frontmatter patch {path}")
    return f"Updated frontmatter in {path}"


# --- validation ---


@mcp.tool()
def validate_markdown(content: str) -> str:
    """Validate markdown content. Returns 'valid' or list of issues."""
    from markdown_it import MarkdownIt

    issues = []

    # frontmatter check
    if content.startswith("---"):
        end = content.find("---", 3)
        if end == -1:
            issues.append("Unclosed frontmatter block")
        else:
            try:
                yaml.safe_load(content[3:end])
            except yaml.YAMLError as e:
                issues.append(f"Invalid frontmatter YAML: {e}")

    # markdown parse (catches unclosed syntax)
    try:
        md = MarkdownIt()
        md.render(content)
    except Exception as e:
        issues.append(f"Markdown parse error: {e}")

    # wikilink format check
    malformed = re.findall(r"\[{2}[^\]]*\]{1}(?!\])|(?<!\[)\[{1}[^\]]*\]{2}", content)
    if malformed:
        issues.append(f"Malformed wikilinks: {malformed}")

    return "valid" if not issues else "\n".join(issues)


@mcp.tool()
def validate_note(path: str) -> str:
    """Validate an existing note: frontmatter, markdown, and internal links"""
    target = VAULT / path
    if not target.exists():
        return f"Not found: {path}"

    content = target.read_text()
    issues = []

    # run markdown validation
    md_result = validate_markdown(content)
    if md_result != "valid":
        issues.append(md_result)

    # check wikilinks point to existing notes
    links = _extract_links(content)
    all_stems = {f.stem for f in _all_md_files()}
    for link in links:
        stem = Path(link).stem
        if stem not in all_stems:
            issues.append(f"Broken link: [[{link}]]")

    return "valid" if not issues else "\n".join(issues)


# --- skills ---


@mcp.tool()
def list_skills() -> str:
    """List available skills with their names and descriptions."""
    if not SKILLS_DIR.exists():
        return "No skills available"
    skills = []
    for skill_file in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        post = frontmatter.loads(skill_file.read_text())
        name = post.metadata.get("name", skill_file.parent.name)
        description = post.metadata.get("description", "")
        skills.append(f"- {name}: {description}")
    return "\n".join(skills) if skills else "No skills available"


@mcp.tool()
def read_skill(name: str) -> str:
    """Load full instructions for a skill by name."""
    if not SKILLS_DIR.exists():
        return f"Skill not found: {name}"
    for skill_file in SKILLS_DIR.glob("*/SKILL.md"):
        post = frontmatter.loads(skill_file.read_text())
        skill_name = str(post.metadata.get("name", skill_file.parent.name))
        if skill_name.lower() == name.lower():
            return skill_file.read_text()
    return f"Skill not found: {name}"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
