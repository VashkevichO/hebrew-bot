import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

with open(DATA_DIR / "alphabet.json", encoding="utf-8") as f:
    ALPHABET = json.load(f)["letters"]

with open(DATA_DIR / "words.json", encoding="utf-8") as f:
    WORDS = json.load(f)["words"]

ALPHABET_BY_ID = {l["id"]: l for l in ALPHABET}


def get_all_letters():
    return ALPHABET


def get_letter_by_id(letter_id):
    return ALPHABET_BY_ID.get(letter_id)


def get_letter_by_char(char):
    for l in ALPHABET:
        if l["letter"] == char:
            return l
    return None


# --- Уровень 1: Алфавит ---

def get_quiz_sound_to_letter(learned_ids=None):
    """Режим: слышу звук → выбираю букву. Возвращает вопрос и варианты."""
    if learned_ids:
        pool = [l for l in ALPHABET if l["id"] in learned_ids]
    else:
        pool = list(ALPHABET)

    if not pool:
        pool = list(ALPHABET)

    correct = random.choice(pool)
    others = [l for l in ALPHABET if l["id"] != correct["id"]]
    options = random.sample(others, min(3, len(others))) + [correct]
    random.shuffle(options)

    return {
        "correct": correct,
        "options": options,
        "prompt": f"{correct['name_ru']} — {correct['letter']}",
        "prompt_text": correct["letter"],
    }


def get_quiz_letter_to_sound(learned_ids=None):
    """Режим: вижу букву → выбираю звук."""
    if learned_ids:
        pool = [l for l in ALPHABET if l["id"] in learned_ids]
    else:
        pool = list(ALPHABET)

    if not pool:
        pool = list(ALPHABET)

    correct = random.choice(pool)

    sounds = ["—", "б", "в", "г", "д", "h", "з", "х", "т", "й",
              "к", "л", "м", "н", "с", "п", "ф", "ц", "р", "ш"]
    options = random.sample(sounds, min(4, len(sounds)))
    if correct["sound"] not in options:
        options[random.randint(0, len(options) - 1)] = correct["sound"]
    random.shuffle(options)

    return {
        "correct": correct,
        "options": options,
        "prompt": correct["letter"],
    }


def get_quiz_sofit(learned_ids=None):
    """Режим: печатная → софит / наоборот."""
    letters_with_sofit = [l for l in ALPHABET if l["sofit"]]
    if not letters_with_sofit:
        return None

    correct = random.choice(letters_with_sofit)
    prompt_type = random.choice(["to_sofit", "from_sofit"])

    if prompt_type == "to_sofit":
        prompt = correct["letter"]
        correct_answer = correct["sofit"]
    else:
        prompt = correct["sofit"]
        correct_answer = correct["letter"]

    all_forms = []
    for l in letters_with_sofit:
        all_forms.append(l["letter"])
        all_forms.append(l["sofit"])
    all_forms = list(set(all_forms))
    all_forms.remove(correct_answer)

    options = random.sample(all_forms, min(3, len(all_forms))) + [correct_answer]
    random.shuffle(options)

    return {
        "correct_char": correct_answer,
        "correct_letter": correct,
        "options": options,
        "prompt": prompt,
        "prompt_type": prompt_type,
    }


# --- Письменные буквы: викторины ---

def get_quiz_script_to_letter():
    """Показываю письменную букву → выбрать печатную."""
    correct = random.choice(ALPHABET)
    others = [l for l in ALPHABET if l["id"] != correct["id"]]
    options = random.sample(others, min(3, len(others))) + [correct]
    random.shuffle(options)
    return {
        "correct": correct,
        "options": options,
    }


def get_quiz_script_to_sound():
    """Показываю письменную букву → выбрать звук."""
    correct = random.choice(ALPHABET)
    sounds = ["—", "б", "в", "г", "д", "h", "з", "х", "т", "й",
              "к", "л", "м", "н", "с", "п", "ф", "ц", "р", "ш"]
    options = random.sample(sounds, min(4, len(sounds)))
    if correct["sound"] not in options:
        options[random.randint(0, len(options) - 1)] = correct["sound"]
    random.shuffle(options)
    return {
        "correct": correct,
        "options": options,
    }


def get_quiz_script_to_name():
    """Показываю письменную букву → выбрать название (по-русски)."""
    correct = random.choice(ALPHABET)
    others = [l for l in ALPHABET if l["id"] != correct["id"]]
    options = random.sample(others, min(3, len(others))) + [correct]
    random.shuffle(options)
    return {
        "correct": correct,
        "options": options,
    }


# --- Уровень 2: Собери слово по звуку ---

def get_word_for_level(learned_ids=None):
    """Возвращает случайное слово (без привязки к изученным буквам)."""
    if not WORDS:
        return None
    return random.choice(WORDS)


def get_scramble_word(learned_ids=None):
    """Перемешивает буквы слова. Уровень 3."""
    word_data = get_word_for_level()
    if not word_data:
        return None

    letters = list(word_data["he"])
    random.shuffle(letters)
    scrambled = "".join(letters)

    # Если перемешалось как исходное — мешаем ещё раз
    if scrambled == word_data["he"] and len(letters) > 1:
        random.shuffle(letters)
        scrambled = "".join(letters)

    return {
        "word": word_data,
        "scrambled": scrambled,
    }


# --- Прогресс и похвала ---

MOTIVATION = [
    "Отлично! 🔥",
    "Красава! 💪",
    "Так держать! ⭐",
    "Ты в огне! 🔥🔥",
    "Буква в копилку! 🎯",
    "Прекрасный результат! 🌟",
    "Умница! 🏆",
    "Ещё одна готова! ✅",
    "Не останавливайся! 🚀",
]


# --- Сосчитай буквы в строке ---

def get_count_letter_quiz():
    """Генерирую строку из 35-45 букв, выбираю букву, пользователь считает."""
    letters_pool = [l["letter"] for l in ALPHABET]
    length = random.randint(35, 45)
    target = random.choice(letters_pool)
    fill_pool = [c for c in letters_pool if c != target]
    if not fill_pool:
        fill_pool = letters_pool
    target_count = random.randint(0, 5)
    text_chars = [target] * target_count
    for _ in range(length - target_count):
        text_chars.append(random.choice(fill_pool))
    random.shuffle(text_chars)
    text = "".join(text_chars)
    l_data = next((l for l in ALPHABET if l["letter"] == target), None)
    return {
        "text": text,
        "letter": target,
        "count": target_count,
        "letter_name": l_data["name_ru"] if l_data else target,
    }


# --- Игра «Соседи»: буквы по алфавиту ---
# Канонический порядок ивритского алфавита (22 буквы):
# парные Bet/Vet, Kaf/Khaf, Pe/Fe, Shin/Sin считаются ОДНОЙ буквой,
# софитные формы (конец слова) — формами той же буквы.

# id записи -> позиция в каноническом алфавите (0..21)
CANONICAL_POS_BY_ID = {
    1: 0, 2: 1, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6, 9: 7, 10: 8,
    11: 9, 12: 10, 13: 10, 14: 10, 15: 11, 16: 12, 17: 12, 18: 13,
    19: 13, 20: 14, 21: 15, 22: 16, 23: 16, 24: 16, 25: 17, 26: 17,
    27: 18, 28: 19, 29: 20, 30: 20, 31: 21,
}

# Позиция -> id репрезентативной записи (чистая форма без дагеша)
CANONICAL_ID_BY_POS = {
    0: 1, 1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11,
    10: 13, 11: 15, 12: 16, 13: 18, 14: 20, 15: 21, 16: 23, 17: 25,
    18: 27, 19: 28, 20: 29, 21: 31,
}


def get_quiz_neighbors():
    """Игра «Соседи»: дана буква → назвать буквы ДО и ПОСЛЕ по алфавиту.

    Буквы выбираем из середины алфавита (позиции 1..20):
    у Алеф нет буквы слева, у Тав — справа.
    Возвращает два вопроса (перед / после) с вариантами ответа.
    """
    pos = random.randint(1, 20)
    target_letter = get_letter_by_id(CANONICAL_ID_BY_POS[pos])
    prev_letter = get_letter_by_id(CANONICAL_ID_BY_POS[pos - 1])
    next_letter = get_letter_by_id(CANONICAL_ID_BY_POS[pos + 1])

    def make_options(correct_letter):
        # дистракторы: другие канонические буквы, но не сама буква
        # и не её соседи (чтобы не было двух «правильных»)
        others = [
            get_letter_by_id(CANONICAL_ID_BY_POS[p])
            for p in range(22)
            if p != pos and p != pos - 1 and p != pos + 1
        ]
        distractors = random.sample(others, 3)
        options = distractors + [correct_letter]
        random.shuffle(options)
        return options

    return {
        "target": target_letter,
        "prev": prev_letter,
        "next": next_letter,
        "prev_options": make_options(prev_letter),
        "next_options": make_options(next_letter),
    }


def get_motivation():
    return random.choice(MOTIVATION)


STREAK_MESSAGES = {
    3: "Три подряд! Комбо ×3 🔥🔥🔥",
    5: "Пять! Ты на волне! ×5 💥",
    10: "ДЕСЯТЬ! Невероятно! ×10 ⚡",
}


def get_streak_message(streak):
    if streak in STREAK_MESSAGES:
        return STREAK_MESSAGES[streak]
    if streak >= 15 and streak % 5 == 0:
        return f"{streak} подряд! Ты машина! ×{streak} 🏆"
    return None


def get_progress_text(learned_ids):
    total = len(ALPHABET)
    count = len(learned_ids)
    percent = int(count / total * 100)
    bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
    return f"Прогресс: {count}/{total} букв ({percent}%)\n{bar}"
