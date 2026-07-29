"""
parse_grokipedia.py  (v2 – tuned to actual Grokipedia HTML)
------------------------------------------------------------
Parses a saved HTML file from grokipedia.com and extracts:
  - Page title
  - Section headers (h2 / h3 / h4) with their anchor IDs
  - The body text of each section
  - References (title + URL)

Grokipedia page structure
--------------------------
All article content lives inside a single <div class="flow-root">.
Its direct children are a flat sequence of:
  <span class="mb-4 block …">     → paragraph text
  <h2 id="…">                    → top-level section header
  <h3 id="…">                    → sub-section header
  <h4 id="…">                    → sub-sub-section header
  <div class="border-border-l1"> → inline data tables
  <div id="references">          → references block (handled separately)

References live in:
  <div id="references">
    <ol> <li id="ref-N"> <a href="…">title</a> </li> … </ol>
  </div>

Usage
------
  python parse_grokipedia.py <file.html> [--json] [--output FILE]

Dependencies
-------------
  pip install beautifulsoup4 lxml

AI usage
-----------
  This script was written with Claude Sonnet 4.6
  It was based off of the HTML of the grokipedia page "Ashkenazi Jews", downloaded via curl on March 24, 2026.
  This was the prompt used:

  I am trying to extract data from HTML pages from the website grokipedia.com.
  I need a python script that takes in an HTML file from grokipedia.com and returns a list of section headers,
  references, and the text within each section.

  This is a sample HTML file. [File attached]
"""

import sys, json, argparse
from pathlib import Path
from bs4 import BeautifulSoup, Tag

PARA_CLASSES      = {"mb-4", "block", "break-words", "leading-[1.85]"}
HEADER_TAGS       = {"h2", "h3", "h4"}
TABLE_WRAPPER_CLS = "border-border-l1"


def _is_paragraph(tag: Tag) -> bool:
    classes = set(tag.get("class") or [])
    return tag.name == "span" and bool(classes & PARA_CLASSES)

def _is_table_block(tag: Tag) -> bool:
    classes = set(tag.get("class") or [])
    return tag.name == "div" and TABLE_WRAPPER_CLS in classes

def _is_header(tag: Tag) -> bool:
    return tag.name in HEADER_TAGS

def _header_text(tag: Tag) -> str:
    """Return heading text, stripping the hidden copy-link icon spans."""
    clone = BeautifulSoup(str(tag), "lxml").find(tag.name)
    for icon in clone.find_all("span", class_=lambda c: c and "opacity-0" in c):
        icon.decompose()
    return clone.get_text(separator=" ", strip=True)


def extract_sections(soup: BeautifulSoup) -> list:
    content_div = soup.find("div", class_="flow-root")
    if content_div is None:
        raise ValueError("Could not find <div class='flow-root'>. Is this a Grokipedia page?")

    sections, current = [], None

    for child in content_div.children:
        if not isinstance(child, Tag):
            continue
        if child.get("id") == "references":
            continue

        if _is_header(child):
            current = {"level": child.name, "header": _header_text(child),
                       "id": child.get("id", ""), "text": ""}
            sections.append(current)

        elif _is_paragraph(child):
            text = child.get_text(separator=" ", strip=True)
            if not text:
                continue
            if current is None:
                current = {"level": "h2", "header": "(Introduction)", "id": "", "text": ""}
                sections.append(current)
            current["text"] += ("\n" if current["text"] else "") + text

        elif _is_table_block(child):
            text = child.get_text(separator=" | ", strip=True)
            if text and current is not None:
                current["text"] += ("\n" if current["text"] else "") + "[TABLE] " + text

    return sections


def extract_references(soup: BeautifulSoup) -> list:
    refs_div = soup.find("div", id="references")
    if not refs_div:
        return []
    ol = refs_div.find("ol")
    if not ol:
        return []
    refs = []
    for li in ol.find_all("li"):
        anchor = li.find("a")
        refs.append({
            "id":    li.get("id", ""),
            "title": anchor.get_text(strip=True) if anchor else li.get_text(strip=True),
            "url":   anchor.get("href") if anchor else None,
        })
    return refs


def parse_grokipedia_html(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "Unknown"
    title = title.replace("— Grokipedia", "").replace("– Grokipedia", "").strip()
    return {
        "title":      title,
        "sections":   extract_sections(soup),
        "references": extract_references(soup),
    }


def format_text(data: dict) -> str:
    SEP = "=" * 70
    lines = [SEP, f"TITLE: {data['title']}", SEP + "\n"]
    indent_map = {"h2": "", "h3": "  ", "h4": "    "}
    for sec in data["sections"]:
        ind = indent_map.get(sec["level"], "")
        anchor = f"  #{sec['id']}" if sec.get("id") else ""
        lines.append(f"{ind}[{sec['level'].upper()}] {sec['header']}{anchor}")
        for para in sec["text"].split("\n"):
            if para:
                lines.append(f"{ind}  {para}")
        lines.append("")
    if data["references"]:
        lines += [SEP, "REFERENCES", SEP]
        for i, ref in enumerate(data["references"], 1):
            url = f"  <{ref['url']}>" if ref.get("url") else ""
            lines.append(f"[{i}] {ref['title']}{url}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Extract content from a Grokipedia HTML file.")
    ap.add_argument("html_file")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--output", metavar="FILE")
    args = ap.parse_args()

    path = Path(args.html_file)
    if not path.exists():
        sys.exit(f"Error: file not found: {path}")

    data   = parse_grokipedia_html(path.read_text(encoding="utf-8", errors="replace"))
    result = json.dumps(data, indent=2, ensure_ascii=False) if args.as_json else format_text(data)

    if args.output:
        Path(args.output).write_text(result, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(result)

if __name__ == "__main__":
    main()