"""Раздел «Важно» (data/important.json): краткие памятки.

Тексты + таблицы. Используется в меню «📌 Важно».
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
IMPORTANT_PATH = DATA_DIR / "important.json"


@lru_cache(maxsize=1)
def load_sections():
    with open(IMPORTANT_PATH, encoding="utf-8") as f:
        return json.load(f)["sections"]


def get_section(section_id):
    for s in load_sections():
        if s["id"] == section_id:
            return s
    return None


def render_section(section):
    """Собирает текст раздела: содержание + таблицы (Markdown)."""
    parts = [f"📌 **{section['title_ru']}**", "", section["content_ru"]]
    for table in section.get("tables", []):
        parts.append("")
        parts.append(f"**{table['title']}**")
        parts.append("")
        header = table["rows"][0]
        parts.append("| " + " | ".join(str(c) for c in header) + " |")
        parts.append("|" + "|".join(["---"] * len(header)) + "|")
        for row in table["rows"][1:]:
            parts.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(parts)
