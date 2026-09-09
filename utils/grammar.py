"""Справочные материалы (data/grammar_reference.json).

Тексты справки + таблицы. Используется в /grammar и для пояснений в тренировках.
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
GRAMMAR_PATH = DATA_DIR / "grammar_reference.json"


@lru_cache(maxsize=1)
def load_sections():
    with open(GRAMMAR_PATH, encoding="utf-8") as f:
        return json.load(f)["sections"]


def get_section(section_id):
    for s in load_sections():
        if s["id"] == section_id:
            return s
    return None


def render_section(section):
    """Собирает текст раздела: содержание + таблицы (Markdown)."""
    parts = [f"📖 **{section['title_ru']}**", "", section["content_ru"]]
    for table in section.get("tables", []):
        parts.append("")
        parts.append(f"**{table['title']}**")
        parts.append("")
        # ширина колонок по первой строке
        header = table["rows"][0]
        parts.append("| " + " | ".join(str(c) for c in header) + " |")
        parts.append("|" + "|".join(["---"] * len(header)) + "|")
        for row in table["rows"][1:]:
            parts.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(parts)
