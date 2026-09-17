"""Generate the CLI reference page from the real argparse tree, so the docs cannot drift.

uv run python scripts/cli_reference.py           # write the page
uv run python scripts/cli_reference.py --check   # exit 1 if the page is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web/apps/site/src/content/docs/reference/cli.mdx"


class _Captured(Exception):
    def __init__(self, parser: argparse.ArgumentParser):
        self.parser = parser


def capture_parser() -> argparse.ArgumentParser:
    """Run the CLI's main() with parse_args replaced, so the parser is handed back untouched."""
    from bio.__main__ import main

    def grab(self: argparse.ArgumentParser, *_a, **_k):
        raise _Captured(self)

    original = argparse.ArgumentParser.parse_args
    argparse.ArgumentParser.parse_args = grab  # type: ignore[method-assign]
    try:
        main([])
    except _Captured as c:
        return c.parser
    finally:
        argparse.ArgumentParser.parse_args = original  # type: ignore[method-assign]
    raise RuntimeError("the CLI never parsed arguments")


def _flag(a: argparse.Action) -> str:
    if a.option_strings:
        name = ", ".join(a.option_strings)
        if a.nargs != 0 and a.metavar is not False:
            name += f" {a.metavar or a.dest.upper()}"
        return name
    if a.nargs in ("+", "*"):
        return f"{a.dest}..."
    return a.dest


def _subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    return next((a for a in parser._actions if isinstance(a, argparse._SubParsersAction)), None)


def _rows(parser: argparse.ArgumentParser) -> list[str]:
    """The argument table for one parser's own options — never its nested subcommands."""
    args = [a for a in parser._actions if not isinstance(a, (argparse._HelpAction, argparse._SubParsersAction))]
    if not args:
        return []
    rows = ["| Argument | Meaning |", "| --- | --- |"]
    for a in args:
        meaning = (a.help or "").rstrip(".")
        if a.choices:
            meaning += (" " if meaning else "") + "One of " + ", ".join(f"`{c}`" for c in a.choices)
        if a.default not in (None, False, argparse.SUPPRESS) and a.option_strings:
            meaning += f" (default `{a.default}`)"
        rows.append(f"| `{_flag(a)}` | {meaning or '—'} |")
    rows.append("")
    return rows


def _section(name: str, parser: argparse.ArgumentParser, help_text: str, level: int) -> list[str]:
    """A command's heading, one-line help, argument table, then each of its subcommands one level
    deeper — so a group like `flasks` lists `flasks new`/`flasks run`/`flasks curve` with their
    flags, not just the bare group entry."""
    lines = [f"{'#' * level} {name}", ""]
    if help_text:
        lines += [help_text[0].upper() + help_text[1:].rstrip(".") + ".", ""]
    lines += _rows(parser)
    subs = _subparsers(parser)
    if subs is not None:
        for child, sub in subs.choices.items():
            child_help = next((c.help for c in subs._choices_actions if c.dest == child), None) or ""
            lines += _section(f"{name} {child}", sub, child_help, level + 1)
    return lines


def render(parser: argparse.ArgumentParser) -> str:
    subs = _subparsers(parser)
    assert subs is not None, "the top-level parser has subcommands"
    lines = [
        "---",
        "title: CLI reference",
        "description: Every biotic command and its arguments.",
        "section: Reference",
        "order: 0",
        "generated: scripts/cli_reference.py",
        "---",
        "",
        "Generated from the command line parser by `scripts/cli_reference.py`; edit the code, not this page.",
        "Run any command as `uv run biotic <command>` from the repository, or `biotic <command>` once installed. Without a command, `biotic` opens the live view if a culture exists.",
        "",
    ]
    for name, sub in subs.choices.items():
        help_text = next((c.help for c in subs._choices_actions if c.dest == name), None) or ""
        lines += _section(name, sub, help_text, 2)
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    text = render(capture_parser())
    if check:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"{OUT.relative_to(ROOT)} is stale; run: uv run python scripts/cli_reference.py", file=sys.stderr)
            return 1
        print("cli reference is current")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
