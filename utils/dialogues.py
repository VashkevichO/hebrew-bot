"""Работа с каталогом диалогов (data/dialogues.json) и недельным циклом.

Недельный цикл: EPOCH = 2026-09-14 (понедельник).
    номер_недели = (сегодня - EPOCH).days // 7
    индекс_диалога = номер_недели % len(dialogues)   (до EPOCH -> 0)
"""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DIALOGUES_PATH = DATA_DIR / "dialogues.json"

# Старт отсчёта недель (согласовано с продуктом: 2026-09-14, понедельник)
EPOCH = date(2026, 9, 14)


@lru_cache(maxsize=1)
def load_dialogues():
    """Загружает список диалогов из JSON (кэш)."""
    with open(DIALOGUES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["dialogues"]


def get_dialogue_by_id(dialogue_id):
    for dlg in load_dialogues():
        if dlg["id"] == dialogue_id:
            return dlg
    return None


def get_week_info(today=None):
    """Возвращает {'week': N, 'index': i} для даты.

    week — номер недели от EPOCH (0 = неделя старта).
    index — индекс диалога в каталоге (week % кол-во). До EPOCH = 0.
    """
    today = today or date.today()
    days = (today - EPOCH).days
    week = max(days, 0) // 7
    dialogues = load_dialogues()
    index = week % len(dialogues) if dialogues else 0
    return {"week": week, "index": index}


def get_dialogue_for_date(today=None):
    """Диалог текущей недели."""
    info = get_week_info(today)
    dialogues = load_dialogues()
    if not dialogues:
        return None, info
    return dialogues[info["index"]], info


def dialogue_text(dialogue):
    """Весь ивритский текст диалога (для поиска корней)."""
    parts = []
    for line in dialogue["lines"]:
        for variant in line["variants"]:
            parts.append(variant["he"])
    return " ".join(parts)


def validate_dialogues(dialogues=None):
    """Проверка целостности каталога: уникальные id, структура линий."""
    dialogues = dialogues if dialogues is not None else load_dialogues()
    ids = [d["id"] for d in dialogues]
    assert len(ids) == len(set(ids)), "дубликаты id диалогов"
    for dlg in dialogues:
        assert dlg.get("title_ru"), f"нет title_ru у {dlg['id']}"
        assert dlg.get("lines"), f"нет реплик у {dlg['id']}"
        for line in dlg["lines"]:
            assert line.get("who") in ("a", "b"), f"who должен быть a/b в {dlg['id']}"
            assert line.get("ru"), f"нет ru перевода в {dlg['id']}"
            assert line.get("variants"), f"нет вариантов в {dlg['id']}"
            for v in line["variants"]:
                assert v.get("he"), f"пустой he в {dlg['id']}"
    return True
