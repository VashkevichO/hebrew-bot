"""Работа с корнями (data/roots.json) и поиск корней в тексте.

Поиск корня в слове — это поиск ПОДПОСЛЕДОВАТЕЛЬНОСТИ, а не подстроки:
между буквами корня могут стоять «вставные» буквы. Но чтобы не ловить
ложные срабатывания, вставки ограничены огласовочными ו/י (как в הולך,
אומר, שלום). Спереди слова допускаются служебные префиксы (до 2 букв),
например ייפתח -> פתח, נשמע -> שמע.

Дополнительно:
- нормализуем конечные буквы (ם->מ, ך->כ, ץ->צ, ף->פ, ן->נ);
- стоп-слова (служебные формы и частые заимствования) не участвуют в поиске.
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
ROOTS_PATH = DATA_DIR / "roots.json"

# Конечные формы -> обычные
SOFIT_MAP = str.maketrans({"ם": "מ", "ך": "כ", "ץ": "צ", "ף": "פ", "ן": "נ"})

# Вставные (огласовочные) буквы, которые могут стоять между корневыми
INSERTIONS = "וי"

# Максимум служебных букв перед первой корневой
MAX_PREFIX = 2

# Стоп-слова: служебные формы и частые заимствования, которые не являются
# производными от корней (иначе дают ложные срабатывания)
STOP_WORDS = {
    "שלכם", "שלך", "שלי", "שלה", "שלהם", "שלהן", "שלנו",   # формы של
    "סופר", "סופרמרקט",                                     # супермаркет (заимствование)
    "בנק", "טלפון", "אוטובוס",                                # частые заимствования
}


@lru_cache(maxsize=1)
def load_roots():
    """Список корней из JSON (кэш)."""
    with open(ROOTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["roots"]


def normalize_letters(s):
    """Заменяет конечные буквы на обычные, убирает всё не-буквенное."""
    return "".join(ch for ch in s.translate(SOFIT_MAP) if "\u05d0" <= ch <= "\u05ea")


def root_letters(root):
    """Буквы корня без точек: ש.ל.ם -> שלמ."""
    return normalize_letters(root)


def _is_root_in_word(letters, word):
    """Проверяет, что буквы корня входят в слово в правильном порядке.

    Спереди допускается до MAX_PREFIX служебных букв; между корневыми
    буквами — только вставные ו/י (не более 2 подряд).
    """
    wl = len(word)
    ll = len(letters)
    if wl < ll:
        return False
    # пробуем разные точки старта (0..MAX_PREFIX)
    for start in range(0, min(MAX_PREFIX, wl - ll) + 1):
        i = start
        ok = True
        for ch in letters:
            if i < wl and word[i] == ch:
                i += 1
            elif (
                i < wl and word[i] in INSERTIONS and i + 1 < wl and word[i + 1] == ch
            ):
                i += 2
            elif (
                i + 1 < wl
                and word[i] in INSERTIONS
                and word[i + 1] in INSERTIONS
                and i + 2 < wl
                and word[i + 2] == ch
            ):
                i += 3
            else:
                ok = False
                break
        if ok:
            # после корня не должно остаться больше 3 хвостовых букв
            if wl - i <= 3:
                return True
    return False


def _is_stop(word_norm):
    """Проверка стоп-слов с учётом служебных префиксов (ל,ב,כ,ה,מ,ש,ת)."""
    if word_norm in STOP_WORDS:
        return True
    for pre in "לבכהמשת":
        if len(word_norm) > 1 and word_norm.startswith(pre) and word_norm[1:] in STOP_WORDS:
            return True
    return False


def root_in_word(root, word):
    """Входит ли корень в слово (с учётом вставок и префиксов)."""
    letters = root_letters(root)
    word_norm = normalize_letters(word)
    if not letters or not word_norm:
        return False
    if _is_stop(word_norm):
        return False
    return _is_root_in_word(letters, word_norm)


def find_roots_in_text(text, roots=None):
    """Ищет в тексте все корни из списка. Возвращает список найденных корней
    в порядке их следования в roots.json."""
    roots = roots if roots is not None else load_roots()
    if not text:
        return []
    words = [w for w in (normalize_letters(x) for x in text.split()) if len(w) >= 3]
    found = []
    for root in roots:
        rl = root_letters(root["root"])
        if not rl:
            continue
        for word in words:
            if root_in_word(root["root"], word):
                found.append(root)
                break
    return found


def find_roots_in_dialogue(dialogue, roots=None):
    """Корни, найденные в тексте диалога."""
    from utils.dialogues import dialogue_text

    return find_roots_in_text(dialogue_text(dialogue), roots=roots)


def find_root_by_query(query, roots=None):
    """Ищет корень по запросу: сам корень (ש.ל.ם / שלם) или слово из его набора."""
    roots = roots if roots is not None else load_roots()
    q = normalize_letters(query)
    if not q:
        return None
    for root in roots:
        if root_letters(root["root"]) == q:
            return root
    for root in roots:
        for word in root["words"]:
            if normalize_letters(word["he"]) == q:
                return root
    return None


def validate_roots(roots=None):
    """Проверка целостности: уникальные корни, есть слова."""
    roots = roots if roots is not None else load_roots()
    keys = [root_letters(r["root"]) for r in roots]
    assert len(keys) == len(set(keys)), "дубликаты корней"
    for r in roots:
        assert r.get("meaning"), f"нет meaning у {r['root']}"
        assert r.get("words"), f"нет слов у {r['root']}"
        for w in r["words"]:
            assert w.get("he") and w.get("ru"), f"битое слово в {r['root']}"
    return True
