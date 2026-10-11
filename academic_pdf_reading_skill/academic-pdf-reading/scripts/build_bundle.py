#!/usr/bin/env python3
"""
build_bundle.py -- derive the standalone Markdown version of this skill.

    python3 scripts/build_bundle.py [OUT.md]

The skill folder is the single source of truth. The bundle is regenerated from
it and must never be edited by hand. Default output: academic-pdf-reading.md in
the current directory.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "academic-pdf-reading.md"
    skill = read("SKILL.md")
    m = re.match(r"^---\n(.*?)\n---\n", skill, re.S)
    if not m:
        sys.exit("SKILL.md has no frontmatter")
    front, body = m.group(1), skill[m.end():]
    version = re.search(r'version:\s*"?([\w.]+)"?', front).group(1)
    date = re.search(r'date:\s*"?([\w.-]+)"?', front).group(1)
    desc = re.search(r"description:\s*(.*)", front).group(1).strip()
    companion = read("references/project_protocol.md")
    script = read("scripts/triage.py")
    if "\n~~~~" in script:
        sys.exit("triage.py contains a ~~~~ line; choose another fence")

    parts = [
        "# academic-pdf-reading v%s (%s) — standalone bundle" % (version, date),
        "",
        "> Generated from the skill folder by `scripts/build_bundle.py`. **Do not "
        "edit by hand**: edit the skill and rebuild. Version string must match "
        "the installed skill's `metadata.version`.",
        "",
        "**When to use:** " + desc,
        "",
        "## How to use this bundle without the installed skill",
        "",
        "1. Extract the script (Part 3) to a writable location:",
        "",
        "```bash",
        "python3 - <<'EOF'",
        "import re",
        "t = open('/mnt/project/academic-pdf-reading.md', encoding='utf-8').read()",
        "s = re.search(r'~~~~python\\n(.*?)\\n~~~~', t, re.S).group(1)",
        "open('/home/claude/triage.py', 'w', encoding='utf-8').write(s)",
        "EOF",
        "```",
        "",
        "   (adjust the first path to wherever this bundle lives).",
        "2. Read `SKILL_DIR/scripts/triage.py` as `/home/claude/triage.py`, and "
        "`SKILL_DIR/references/project_protocol.md` as Part 2 below.",
        "",
        "---",
        "",
        "# Part 1 — SKILL.md",
        "",
        body.strip(),
        "",
        "---",
        "",
        "# Part 2 — references/project_protocol.md",
        "",
        companion.strip(),
        "",
        "---",
        "",
        "# Part 3 — scripts/triage.py",
        "",
        "~~~~python",
        script.rstrip("\n"),
        "~~~~",
        "",
    ]
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print("wrote %s (v%s)" % (out, version))


if __name__ == "__main__":
    main()
