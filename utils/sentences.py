"""Упражнения «Собери предложение» (data/sentence_exercises.json).

Проверка строго по шаблонам correct_patterns. Анализ ошибок упрощённый:
extra_word / missing_word / wrong_order — тексты фидбека берутся из данных.
"""
import json
import random
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
EXERCISES_PATH = DATA_DIR / "sentence_exercises.json"


@lru_cache(maxsize=1)
def load_exercises():
    with open(EXERCISES_PATH, encoding="utf-8") as f:
        return json.load(f)["exercises"]


def random_exercise(exercises=None):
    exercises = exercises if exercises is not None else load_exercises()
    return random.choice(exercises)


def _allowed_words(ex):
    """Все слова, которые могут входить в правильное предложение."""
    allowed = set()
    for pattern in ex["correct_patterns"]:
        allowed.update(pattern)
    return allowed


def _base_words(ex):
    """Обязательные слова: присутствуют во всех правильных шаблонах."""
    if not ex["correct_patterns"]:
        return set()
    base = set(ex["correct_patterns"][0])
    for pattern in ex["correct_patterns"][1:]:
        base &= set(pattern)
    return base


def check_sentence(ex, selected):
    """Проверяет собранное предложение.

    selected — список слов в выбранном порядке.
    Возвращает dict: {"ok": bool, "feedback_type": str|None, "text": str|None}
    """
    if selected in ex["correct_patterns"]:
        return {"ok": True, "feedback_type": None, "text": None}

    allowed = _allowed_words(ex)
    # лишние слова (не входят ни в один правильный шаблон)
    extra = [w for w in selected if w not in allowed]
    if extra:
        return {"ok": False, "feedback_type": "extra_word", "text": ex["feedback"].get("extra_word", "")}

    # не хватает обязательных слов
    missing = [w for w in _base_words(ex) if w not in selected]
    if missing:
        return {"ok": False, "feedback_type": "missing_word", "text": ex["feedback"].get("missing_word", "")}

    # те же слова, но другой порядок
    return {"ok": False, "feedback_type": "wrong_order", "text": ex["feedback"].get("wrong_order", "")}


def shuffled_words(ex):
    """Слова упражнения в случайном порядке (для кнопок)."""
    words = ex["words"][:]
    random.shuffle(words)
    return words
