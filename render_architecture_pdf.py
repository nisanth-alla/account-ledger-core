#!/usr/bin/env python3
"""Render ARCHITECTURE.md as a compact four-page PDF using Ghostscript."""

from __future__ import annotations

import re
import subprocess
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "ARCHITECTURE.md"
OUTPUT = ROOT / "ARCHITECTURE.pdf"


def ascii_text(text: str) -> str:
    substitutions = {
        "—": "-", "–": "-", "’": "'", "‘": "'", "“": '"', "”": '"',
        "…": "...", "×": "x", "≤": "<=", "≥": ">=", "→": "->",
    }
    for source, replacement in substitutions.items():
        text = text.replace(source, replacement)
    return text.encode("ascii", "replace").decode("ascii")


def clean_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", text)
    return ascii_text(text)


def parse_sections(markdown: str) -> tuple[str, list[tuple[str, list[str]]]]:
    title = "Architecture & Trade-offs"
    sections: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            title = clean_markdown(line[2:].strip())
        elif line.startswith("## "):
            if current_title is not None:
                sections.append((current_title, current_lines))
            current_title = clean_markdown(line[3:].strip())
            current_lines = []
        elif current_title is not None:
            current_lines.append(line)
    if current_title is not None:
        sections.append((current_title, current_lines))
    if len(sections) != 4:
        raise ValueError(f"Expected four top-level architecture sections, found {len(sections)}")
    return title, sections


def escape_postscript(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def draw_text(y: float, text: str, font: str = "Helvetica", size: float = 9.6,
              x: float = 56) -> str:
    return (f"/{font} findfont {size:.1f} scalefont setfont\n"
            f"{x:.1f} {y:.1f} moveto ({escape_postscript(text)}) show\n")


def body_commands(lines: list[str], start_y: float) -> tuple[str, float]:
    commands = ""
    y = start_y
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal commands, y, paragraph
        if not paragraph:
            return
        text = clean_markdown(" ".join(part.strip() for part in paragraph))
        wrapped = textwrap.wrap(text, width=91, break_long_words=False, break_on_hyphens=False)
        for wrapped_line in wrapped:
            commands += draw_text(y, wrapped_line)
            y -= 12.4
        y -= 5
        paragraph = []

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            flush_paragraph()
            y -= 2
        elif stripped.startswith("### "):
            flush_paragraph()
            heading = clean_markdown(stripped[4:])
            commands += draw_text(y, heading, "Helvetica-Bold", 11.2)
            y -= 16
        elif stripped.startswith("- ") or re.match(r"^\d+\. ", stripped):
            flush_paragraph()
            text = clean_markdown(stripped)
            wrapped = textwrap.wrap(text, width=88, subsequent_indent="   ",
                                    break_long_words=False, break_on_hyphens=False)
            for wrapped_line in wrapped:
                commands += draw_text(y, wrapped_line)
                y -= 12.4
            y -= 3
        else:
            paragraph.append(stripped)
    flush_paragraph()
    return commands, y


def build_postscript(title: str, sections: list[tuple[str, list[str]]]) -> str:
    commands = [
        "%!PS-Adobe-3.0",
        f"%%Pages: {len(sections)}",
        "%%BoundingBox: 0 0 612 792",
        "<< /PageSize [612 792] >> setpagedevice",
    ]
    for page_number, (section_title, lines) in enumerate(sections, start=1):
        commands.append(f"%%Page: {page_number} {page_number}")
        if page_number == 1:
            commands.append(draw_text(754, title, "Helvetica-Bold", 20))
            commands.append(draw_text(738, "Account Ledger Core | Architecture review", "Helvetica", 9))
            commands.append("0.5 setlinewidth 56 726 moveto 556 726 lineto stroke")
            start_y = 704
        else:
            commands.append(draw_text(756, "ACCOUNT LEDGER CORE  |  ARCHITECTURE & TRADE-OFFS",
                                      "Helvetica", 8.5))
            commands.append("0.5 setlinewidth 56 744 moveto 556 744 lineto stroke")
            start_y = 718
        commands.append(draw_text(start_y, section_title, "Helvetica-Bold", 15.5))
        body, final_y = body_commands(lines, start_y - 25)
        if final_y < 42:
            raise ValueError(
                f"Section {section_title!r} does not fit on one page (bottom y={final_y:.1f})"
            )
        commands.append(body)
        commands.append(draw_text(28, f"Page {page_number} of {len(sections)}", "Helvetica", 8.5))
        commands.extend(["showpage", f"%%EndPage: {page_number} {page_number}"])
    commands.append("%%EOF")
    return "\n".join(commands)


def main() -> None:
    title, sections = parse_sections(SOURCE.read_text(encoding="utf-8"))
    postscript = build_postscript(title, sections)
    with tempfile.TemporaryDirectory(prefix="ledger-pdf-") as temp_dir:
        ps_path = Path(temp_dir) / "architecture.ps"
        ps_path.write_text(postscript, encoding="ascii")
        subprocess.run(["ps2pdf", str(ps_path), str(OUTPUT)], check=True)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
