"""Работа с глаголами (data/verbs.json): тренировка «Спряжение по местоимению».

Местоимения для вопросов — только однозначные по роду (без אני/אנחנו,
т.к. их форма зависит от пола говорящего).
"""
import json
import random
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
VERBS_PATH = DATA_DIR / "verbs.json"

# Местоимение -> ключ формы в present
PRONOUNS = [
    {"he": "אתה", "ru": "ты (м.)", "form": "male_sg"},
    {"he": "את", "ru": "ты (ж.)", "form": "female_sg"},
    {"he": "הוא", "ru": "он", "form": "male_sg"},
    {"he": "היא", "ru": "она", "form": "female_sg"},
    {"he": "אתם", "ru": "вы (м.)", "form": "male_pl"},
    {"he": "אתן", "ru": "вы (ж.)", "form": "female_pl"},
    {"he": "הם", "ru": "они (м.)", "form": "male_pl"},
    {"he": "הן", "ru": "они (ж.)", "form": "female_pl"},
]

# Ключ формы -> пояснение (род, число, местоимения)
FORM_INFO = {
    "male_sg": {"label": "мужской род, единственное число", "pronouns": "אתה, הוא"},
    "female_sg": {"label": "женский род, единственное число", "pronouns": "את, היא"},
    "male_pl": {"label": "мужской род, множественное число", "pronouns": "אתם, הם"},
    "female_pl": {"label": "женский род, множественное число", "pronouns": "אתן, הן"},
}


@lru_cache(maxsize=1)
def load_verbs():
    with open(VERBS_PATH, encoding="utf-8") as f:
        return json.load(f)["verbs"]


def get_verb_by_root(root):
    for v in load_verbs():
        if v["root"] == root:
            return v
    return None


def _root_letters(root):
    """Корень без точек и с нормализацией конечных: ה.ל.ך -> הלכ (как в roots)."""
    sofit = str.maketrans({"ם": "מ", "ך": "כ", "ץ": "צ", "ף": "פ", "ן": "נ"})
    return "".join(ch for ch in root.translate(sofit) if "\u05d0" <= ch <= "\u05ea")


def find_verbs_by_root_letters(letters):
    """Все глаголы, чей корень (без точек) равен letters."""
    found = []
    for v in load_verbs():
        if _root_letters(v["root"]) == letters:
            found.append(v)
    return found


def form_for(verb, form_key):
    """Форма глагола по ключу (male_sg и т.д.)."""
    return verb["present"][form_key]


def unique_forms(verb):
    """Уникальные формы глагола: 4 формы present + инфинитив (без дублей)."""
    forms = [verb["present"][k] for k in ("male_sg", "female_sg", "male_pl", "female_pl")]
    unique = list(dict.fromkeys(forms))  # убираем дубли, сохраняя порядок
    unique.append(verb["infinitive"])
    return list(dict.fromkeys(unique))


def build_question(verbs=None):
    """Собирает вопрос тренировки.

    Возвращает dict:
      verb, pronoun_he, pronoun_ru, correct, options (4 шт), correct_index
    """
    verbs = verbs if verbs is not None else load_verbs()
    verb = random.choice(verbs)
    pronoun = random.choice(PRONOUNS)
    correct = form_for(verb, pronoun["form"])

    # пул дистракторов: другие формы этого глагола + инфинитив
    distractors = [f for f in unique_forms(verb) if f != correct]
    # если мало — добавить формы случайных других глаголов
    pool = distractors[:]
    other = [v for v in verbs if v["infinitive"] != verb["infinitive"]]
    while len(pool) < 3 and other:
        v = random.choice(other)
        other.remove(v)
        for f in unique_forms(v):
            if f != correct and f not in pool:
                pool.append(f)
                break

    wrong = random.sample(pool[:20], min(3, len(pool)))
    options = wrong + [correct]
    random.shuffle(options)

    return {
        "verb": verb,
        "pronoun_he": pronoun["he"],
        "pronoun_ru": pronoun["ru"],
        "correct": correct,
        "options": options,
        "correct_index": options.index(correct),
    }


def explain_form(form_key):
    """Пояснение к форме (берётся из FORM_INFO, не дублируется в данных)."""
    info = FORM_INFO[form_key]
    return f"{info['label']}. Эта форма используется с: {info['pronouns']}."


def explain_answer(pronoun_he, correct):
    """Краткое пояснение после ответа: почему эта форма верна."""
    for p in PRONOUNS:
        if p["he"] == pronoun_he:
            info = FORM_INFO[p["form"]]
            return (
                f"«{correct}» — {info['label']}. "
                f"Местоимение {pronoun_he} ({p['ru']}) требует этой формы."
            )
    return ""
