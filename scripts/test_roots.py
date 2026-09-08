"""Тесты корней и поиска по тексту (pytest).

Запуск: python -m pytest scripts/test_roots.py -v
"""
import pytest

from utils import roots


def test_load_roots_has_entries():
    data = roots.load_roots()
    assert len(data) >= 20
    # ключевые корни на месте (root_letters нормализует конечные: ך->כ)
    keys = {roots.root_letters(r["root"]) for r in data}
    for expected in ("שלמ", "הלכ", "קרא"):
        assert expected in keys


def test_validate_roots():
    assert roots.validate_roots() is True


# ===== Поиск корня в слове (подпоследовательность) =====

@pytest.mark.parametrize("root, word, expected", [
    ("ה.ל.ך", "הולך", True),      # вставная ו
    ("ה.ל.ך", "הלך", True),       # прямое вхождение
    ("א.מ.ר", "אומר", True),      # вставная ו
    ("א.מ.ר", "אמר", True),
    ("ש.ל.ם", "שלום", True),      # конечная ם
    ("ש.ל.ם", "להשלים", True),    # префикс ל,ה + вставная י
    ("ב.ו.א", "יבוא", True),      # будущее: יבוא
    ("פ.ת.ח", "ייפתח", True),     # ייפתח (будущее), префикс יי
    ("ש.מ.ע", "נשמע", True),      # префикс נ
    ("ק.ר.א", "קוראים", True),    # קוראים (зовут)
    ("ש.מ.ע", "שמעה", True),
    # отрицательные: ложные срабатывания
    ("ש.ל.ם", "של", False),       # мало букв
    ("ש.ל.ם", "שלכם", False),     # של + суффикс (стоп-слово)
    ("ס.פ.ר", "לסופר", False),    # супермаркет (стоп-слово)
    ("ר.א.ה", "בית", False),
    ("ק.ר.א", "מאוד", False),
    ("ס.ד.ר", "מסתדרת", False),   # согласная ת в середине — не вставка
])
def test_root_in_word(root, word, expected):
    assert roots.root_in_word(root, word) is expected


# ===== Поиск корней в тексте =====

def test_find_roots_in_d1_text():
    text = "שלום! מה נשמע? הכול בסדר, תודה. הולך לסופר. להתראות מחר."
    found = roots.find_roots_in_text(text)
    keys = {roots.root_letters(r["root"]) for r in found}
    assert "שלמ" in keys      # שלום
    assert "סדר" in keys      # בסדר
    assert "הלכ" in keys      # הולך (ключ нормализован: ך->כ)
    assert "שמע" in keys      # נשמע
    assert "ספר" not in keys  # לסופר — стоп-слово


def test_find_roots_empty_text():
    assert roots.find_roots_in_text("") == []
    assert roots.find_roots_in_text("   ") == []


# ===== Поиск корня по запросу =====

def test_find_root_by_root_string():
    r = roots.find_root_by_query("ש.ל.ם")
    assert r and r["root"] == "ש.ל.ם"


def test_find_root_by_letters_no_dots():
    r = roots.find_root_by_query("שלמ")
    assert r and r["root"] == "ש.ל.ם"


def test_find_root_by_word():
    r = roots.find_root_by_query("שלום")
    assert r and r["root"] == "ש.ל.ם"


def test_find_root_miss():
    assert roots.find_root_by_query("מקרר") is None
    assert roots.find_root_by_query("") is None


# ===== Корни в диалоге =====

def test_roots_in_real_dialogue_d01():
    from utils.dialogues import get_dialogue_by_id

    dlg = get_dialogue_by_id("d01")
    found = roots.find_roots_in_dialogue(dlg)
    keys = {roots.root_letters(r["root"]) for r in found}
    assert "שלמ" in keys
    assert "סדר" in keys
    assert "הלכ" in keys
