import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

AUDIO_DIR = BASE_DIR / "assets" / "audio"
ASSETS_DIR = BASE_DIR / "assets"

with open(Path(__file__).parent / "data" / "alphabet.json", encoding="utf-8") as f:
    ALL_LETTERS = json.load(f)["letters"]
ALPHABET_BY_NAME = {l["name_en"].lower(): l for l in ALL_LETTERS}


def get_audio_path(en_name):
    letter = ALPHABET_BY_NAME.get(en_name.lower())
    if letter and letter.get("audio_file"):
        return AUDIO_DIR / letter["audio_file"]
    return AUDIO_DIR / f"{en_name.lower().replace(' ', '_')}.mp3"

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from utils.database import (
    init_db,
    register_user,
    get_learned_letters,
    mark_letter_learned,
    add_points,
    get_stats,
    reset_streak,
)
from utils.logic import (
    get_all_letters,
    get_letter_by_id,
    get_quiz_sound_to_letter,
    get_quiz_letter_to_sound,
    get_quiz_sofit,
    get_quiz_script_to_letter,
    get_quiz_script_to_sound,
    get_quiz_script_to_name,
    get_count_letter_quiz,
    get_quiz_neighbors,
    get_word_for_level,
    get_scramble_word,
    get_motivation,
    get_streak_message,
    get_progress_text,
)
from utils.tts import generate_word_audio

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN", "")

if not TOKEN:
    print(
        "ОШИБКА: не найден BOT_TOKEN в файле .env. "
        "Скопируйте .env.example в .env и вставьте токен от @BotFather."
    )
    sys.exit(1)


async def _send_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, audio_path):
    """Отправляет голосовое сообщение, удалив предыдущее."""
    chat_id = update.effective_chat.id
    last = context.user_data.pop("last_voice_id", None)
    if last:
        try:
            await context.bot.delete_message(chat_id, last)
        except Exception:
            pass
    with open(audio_path, "rb") as f:
        msg = await context.bot.send_voice(chat_id, f)
    context.user_data["last_voice_id"] = msg.message_id


async def _send_script_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, image_path):
    """Отправляет изображение письменной буквы, удалив предыдущее."""
    chat_id = update.effective_chat.id
    last = context.user_data.pop("last_script_photo_id", None)
    if last:
        try:
            await context.bot.delete_message(chat_id, last)
        except Exception:
            pass
    with open(image_path, "rb") as f:
        msg = await context.bot.send_photo(chat_id, f)
    context.user_data["last_script_photo_id"] = msg.message_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, update.effective_chat.id, user.full_name)

    text = (
        f"👋 {user.full_name}, добро пожаловать в Hebrew Alphabet Bot!\n\n"
        "Я помогу тебе выучить алфавит иврита и научиться читать слова.\n\n"
        "📌 **Уровень 1** — Алфавит (звук→буква, буква→звук, софиты)\n"
        "📌 **Уровень 2** — Собери слово по звуку\n"
        "📌 **Уровень 3** — Перепутанные буквы\n\n"
        "Выбери уровень:"
    )

    keyboard = [
        [InlineKeyboardButton("🔤 Алфавит (ур.1)", callback_data="menu_alphabet")],
        [InlineKeyboardButton("🔊 Собери слово (ур.2)", callback_data="menu_build")],
        [InlineKeyboardButton("🔢 Сосчитай буквы", callback_data="menu_count")],
        # [InlineKeyboardButton("🌀 Перепутанные буквы (ур.3)", callback_data="menu_scramble")],
        [InlineKeyboardButton("📊 Мой прогресс", callback_data="menu_progress")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    if data == "menu_alphabet":
        keyboard = [
            [InlineKeyboardButton("📖 Знакомство с буквами", callback_data="explore_list")],
            [InlineKeyboardButton("🔊 Звук → буква", callback_data="quiz_sound")],
            [InlineKeyboardButton("👁️ Буква → звук", callback_data="quiz_letter")],
            [InlineKeyboardButton("🖊️ Письменная → печатная", callback_data="menu_script")],
            [InlineKeyboardButton("🧭 Соседи по алфавиту", callback_data="menu_neighbors")],
            # [InlineKeyboardButton("🔄 Печатная → Софит", callback_data="quiz_sofit")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")],
        ]
        await query.edit_message_text(
            "🔤 **Уровень 1 — Алфавит**\nВыбери режим:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "menu_neighbors":
        keyboard = [
            [InlineKeyboardButton("🔤 Печатные буквы", callback_data="quiz_nb_print")],
            [InlineKeyboardButton("🖊️ Письменные буквы", callback_data="quiz_nb_script")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_alphabet")],
        ]
        await query.edit_message_text(
            "🧭 **Соседи по алфавиту**\n\n"
            "Дана буква — угадай, какие буквы стоят **до** и **после** неё.\n\n"
            "📌 Соседи считаются по классическому алфавиту (22 буквы): "
            "Вэт и Бэт — одна буква, Хаф и Каф — одна и т.д.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "menu_script":
        keyboard = [
            [InlineKeyboardButton("🖊️ Письменная → печатная", callback_data="quiz_script_letter")],
            [InlineKeyboardButton("🖊️ Письменная → звук", callback_data="quiz_script_sound")],
            [InlineKeyboardButton("🖊️ Письменная → название", callback_data="quiz_script_name")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_alphabet")],
        ]
        await query.edit_message_text(
            "✏️ **Письменные буквы**\nСопоставь письменный вариант:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "menu_build":
        word_data = get_word_for_level()
        if not word_data:
            await query.edit_message_text(
                "😅 Нет слов в словаре.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]),
            )
            return

        context.user_data["current_word"] = word_data
        context.user_data["build_attempt"] = []
        context.user_data["build_letters"] = list(word_data["he"])

        audio_path = await generate_word_audio(word_data["he"])
        await _send_voice(update, context, audio_path)

        await query.edit_message_text(
            f"🔊 Собери слово!\n\nСлово из {len(word_data['he'])} букв.\n"
            f"Подсказка: {word_data['ru']}\n\n"
            "Собрано: —\nНажимай буквы по порядку:",
            reply_markup=_build_keyboard(word_data["he"], "build"),
        )

    elif data == "menu_scramble":
        scramble_data = get_scramble_word()
        if not scramble_data:
            await query.edit_message_text(
                "😅 Нет слов в словаре.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]),
            )
            return

        word_data = scramble_data["word"]
        scrambled = scramble_data["scrambled"]
        context.user_data["scramble_word"] = word_data
        context.user_data["scramble_attempt"] = []
        context.user_data["scramble_letters"] = list(scrambled)
        context.user_data["scramble_original"] = list(scrambled)

        await query.edit_message_text(
            f"🌀 **Перепутанные буквы**\n\n"
            f"Буквы: {' · '.join(scrambled)}\n"
            f"Подсказка: {word_data['ru']}\n\n"
            "Собрано: —",
            reply_markup=_build_keyboard(scrambled, "scramble"),
        )

    elif data == "explore_list":
        buttons = []
        row = []
        for l in ALL_LETTERS:
            row.insert(0, InlineKeyboardButton(l["letter"], callback_data=f"explore_{l['id']}"))
            if len(row) == 7:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_alphabet")])

        await query.edit_message_text(
            "📖 **Знакомство с алфавитом**\n\nВыбери букву:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown",
        )

    elif data.startswith("explore_"):
        lid = int(data.split("_")[1])
        letter = [l for l in ALL_LETTERS if l["id"] == lid][0]

        sofit_info = f"\n🔁 Софит: {letter['sofit']}" if letter['sofit'] else ""
        sound_info = f"🔊 Звук: {letter['sound']}" if letter['sound'] != "—" else "🔇 Беззвучная"

        text = (
            f"📖 **{letter['name_ru']} ({letter['name_en']})**\n\n"
            f"✏️ Печатная: {letter['letter']}{sofit_info}\n"
            f"{sound_info}\n"
            f"🔢 Числовое значение: {letter['numeric']}\n"
            f"📝 {letter['comment']}"
        )

        script_path = letter.get("script_image")
        if script_path:
            full_path = ASSETS_DIR / script_path
            if full_path.exists():
                await _send_script_photo(update, context, full_path)

        audio_path = get_audio_path(letter["name_en"])
        if audio_path.exists():
            await _send_voice(update, context, audio_path)

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад к списку", callback_data="explore_list")],
                [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
            ]),
            parse_mode="Markdown",
        )

    elif data == "menu_progress":
        learned = get_learned_letters(user_id)
        stats = get_stats(user_id)
        text = get_progress_text(learned)
        if stats:
            text += f"\n\n⭐ Очки: {stats['total_points']}\n"
            text += f"🔥 Серия: {stats['current_streak']}\n"
            text += f"🏆 Лучшая серия: {stats['best_streak']}"
        text += "\n\nВыученные буквы: "
        learned_letters = [get_letter_by_id(lid) for lid in learned]
        letters_str = " ".join([l["letter"] for l in learned_letters if l])
        text += letters_str if letters_str else "—"

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
            ]),
        )

    elif data == "menu_count":
        quiz = get_count_letter_quiz()
        if not quiz:
            await query.edit_message_text("😅 Что-то пошло не так.")
            return

        context.user_data["count_quiz"] = quiz
        text = (
            f"🔢 **Сосчитай буквы!**\n\n"
            f"Строка: **{quiz['text']}**\n"
            f"Сколько раз встречается буква **{quiz['letter']}** ({quiz['letter_name']})?"
        )

        max_count = min(quiz["count"] + 3, 8)
        buttons = [[
            InlineKeyboardButton(str(n), callback_data=f"ans_count_{n}")
            for n in range(0, max_count + 1)
        ]]
        buttons.append([InlineKeyboardButton("🔙 В меню", callback_data="menu_main")])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown",
        )

    elif data == "menu_main":
        await start(update, context)

    return


def _build_keyboard(letters, prefix):
    """Создаёт inline-клавиатуру для букв (build/scramble)."""
    buttons = []
    for i, letter in enumerate(letters):
        buttons.append(
            InlineKeyboardButton(letter, callback_data=f"{prefix}_{i}_{letter}")
        )
    kb = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    done_data = f"{prefix}_done"
    back_data = f"menu_{prefix}"
    kb.append([InlineKeyboardButton("✅ Готово", callback_data=done_data)])
    kb.append([InlineKeyboardButton("❌ Отмена", callback_data=back_data)])
    return InlineKeyboardMarkup(kb)


async def quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "quiz_sound":
        quiz = get_quiz_sound_to_letter()
        correct = quiz["correct"]
        context.user_data["quiz_correct_id"] = correct["id"]

        audio_path = get_audio_path(correct["name_en"])
        if audio_path.exists():
            await _send_voice(update, context, audio_path)
        else:
            await query.message.reply_text(f"Буква: {correct['letter']} — {correct['name_ru']}")

        keyboard = []
        row = []
        for opt in quiz["options"]:
            row.append(InlineKeyboardButton(opt["letter"], callback_data=f"ans_{opt['id']}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_alphabet")])

        await query.edit_message_text(
            "🎵 **Какой букве принадлежит этот звук?**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "quiz_letter":
        quiz = get_quiz_letter_to_sound()
        correct = quiz["correct"]
        context.user_data["quiz_correct_id"] = correct["id"]

        keyboard = []
        row = []
        for s in quiz["options"]:
            label = correct["sound"] if s == correct["sound"] else s
            row.append(InlineKeyboardButton(s, callback_data=f"ans_sound_{s}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_alphabet")])

        await query.edit_message_text(
            f"👁️ **Буква:** {correct['letter']}\n\nКакой звук она даёт?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data in ("quiz_nb_print", "quiz_nb_script"):
        mode = "script" if data == "quiz_nb_script" else "print"
        context.user_data["nb_mode"] = mode
        quiz = get_quiz_neighbors()
        context.user_data["nb_quiz"] = quiz
        context.user_data["nb_stage"] = "prev"

        target = quiz["target"]
        prompt = "Какая буква стоит **ПЕРЕД** этой?"

        if mode == "script":
            script_path = target.get("script_image")
            if script_path:
                full_path = ASSETS_DIR / script_path
                if full_path.exists():
                    await _send_script_photo(update, context, full_path)
            header = "Целевая буква показана на изображении выше."
        else:
            header = f"Целевая буква: **{target['letter']}** ({target['name_ru']})"

        keyboard = []
        row = []
        for opt in quiz["prev_options"]:
            label = f"{opt['letter']} {opt['name_ru']}"
            cb = f"ans_nb_prev_{opt['id']}"
            row.append(InlineKeyboardButton(label, callback_data=cb))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_neighbors")])

        await query.edit_message_text(
            f"🧭 **{prompt}**\n\n{header}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data in ("quiz_script_letter", "quiz_script_sound", "quiz_script_name"):
        mode = data.split("_")[2]  # letter, sound, name
        context.user_data["script_quiz_mode"] = mode

        if mode == "letter":
            quiz = get_quiz_script_to_letter()
            prompt = "Какой печатной букве соответствует эта письменная?"
            btn_key = "letter"
        elif mode == "sound":
            quiz = get_quiz_script_to_sound()
            prompt = "Какой звук даёт эта письменная буква?"
            btn_key = "sound"
        else:
            quiz = get_quiz_script_to_name()
            prompt = "Как называется эта письменная буква?"
            btn_key = "name"

        correct = quiz["correct"]
        context.user_data["script_correct_id"] = correct["id"]

        script_path = correct.get("script_image")
        if script_path:
            full_path = ASSETS_DIR / script_path
            if full_path.exists():
                await _send_script_photo(update, context, full_path)

        keyboard = []
        row = []
        for opt in quiz["options"]:
            if btn_key == "sound":
                label = correct["sound"] if opt == correct["sound"] else opt
                cb = f"ans_script_sound_{opt}"
            elif btn_key == "name":
                label = opt["name_ru"]
                cb = f"ans_script_name_{opt['id']}"
            else:
                label = opt["letter"]
                cb = f"ans_script_letter_{opt['id']}"
            row.append(InlineKeyboardButton(label, callback_data=cb))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_script")])

        await query.edit_message_text(
            f"✏️ **{prompt}**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "quiz_sofit":
        quiz = get_quiz_sofit()
        if not quiz:
            await query.edit_message_text("Нет букв с софитами для теста.")
            return

        context.user_data["sofit_correct_char"] = quiz["correct_char"]
        context.user_data["sofit_letter_id"] = quiz["correct_letter"]["id"]

        keyboard = []
        row = []
        for opt in quiz["options"]:
            row.append(InlineKeyboardButton(opt, callback_data=f"ans_sofit_{opt}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_alphabet")])

        await query.edit_message_text(
            f"🔄 **Найди пару:**\n\n`{quiz['prompt']}` → ?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    return


async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("ans_"):
        parts = data.split("_", 2)
        if len(parts) < 2:
            return

        # --- Сосчитай буквы ---
        if parts[1] == "count":
            answer = int(parts[2])
            quiz = context.user_data.get("count_quiz", {})
            correct = quiz.get("count", 0)

            if answer == correct:
                add_points(user_id, 15)
                text = f"{get_motivation()} В строке **{quiz['text']}** буква **{quiz['letter']}** встречается **{correct}** раз!"
                keyboard = [
                    [InlineKeyboardButton("🔁 Ещё", callback_data="menu_count")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
            else:
                text = f"❌ Неверно. В строке **{quiz['text']}** буква **{quiz['letter']}** встречается **{correct}** раз."
                keyboard = [
                    [InlineKeyboardButton("🔁 Попробовать ещё", callback_data="menu_count")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        # --- Соседи по алфавиту ---
        if parts[1] == "nb":
            nb_parts = data.split("_")
            stage = nb_parts[2]  # prev / next
            answer_id = int(nb_parts[3])
            quiz = context.user_data.get("nb_quiz", {})
            mode = context.user_data.get("nb_mode", "print")
            target = quiz.get("target")

            if stage == "prev":
                correct = quiz.get("prev")
                next_stage = "next"
                next_options = quiz.get("next_options", [])
                next_q = "А какая буква стоит **ПОСЛЕ** этой?"
            else:
                correct = quiz.get("next")
                next_stage = None
                next_options = []
                next_q = ""

            if answer_id == correct["id"]:
                add_points(user_id, 10)
                if stage == "prev":
                    text = f"✅ **Верно!** Перед буквой **{target['letter']}** стоит **{correct['letter']}** ({correct['name_ru']}). +10 очков"
                else:
                    text = f"✅ **Верно!** После буквы **{target['letter']}** стоит **{correct['letter']}** ({correct['name_ru']}). +10 очков"
            else:
                reset_streak(user_id)
                if stage == "prev":
                    text = f"❌ Неверно. Перед буквой **{target['letter']}** стоит **{correct['letter']}** ({correct['name_ru']})."
                else:
                    text = f"❌ Неверно. После буквы **{target['letter']}** стоит **{correct['letter']}** ({correct['name_ru']})."

            if next_stage == "next":
                # строим кнопки для второго вопроса
                text += "\n\n" + next_q
                keyboard = []
                row = []
                for opt in next_options:
                    label = f"{opt['letter']} {opt['name_ru']}"
                    cb = f"ans_nb_next_{opt['id']}"
                    row.append(InlineKeyboardButton(label, callback_data=cb))
                    if len(row) == 2:
                        keyboard.append(row)
                        row = []
                if row:
                    keyboard.append(row)
                keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="menu_main")])
            else:
                # оба ответа даны — кнопки «Ещё» и «В меню»
                back_data = "quiz_nb_script" if mode == "script" else "quiz_nb_print"
                keyboard = [
                    [InlineKeyboardButton("🔁 Ещё", callback_data=back_data)],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]

            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        # --- Письменная → звук ---
        if parts[1] == "script" and parts[2].startswith("sound_"):
            answer_sound = data.split("_", 3)[3]
            correct_id = context.user_data.get("script_correct_id")
            correct_letter = get_letter_by_id(correct_id)
            correct_sounds = correct_letter["sound"].split("/") if correct_letter else []

            if answer_sound == correct_letter["sound"] or answer_sound in correct_sounds:
                mark_letter_learned(user_id, correct_id)
                add_points(user_id, 10)
                text = f"{get_motivation()} **{correct_letter['letter']}** — {correct_letter['name_ru']}!"
                keyboard = [
                    [InlineKeyboardButton("🔁 Ещё", callback_data="quiz_script_sound")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
            else:
                text = f"❌ Неверно. Правильный звук: {correct_letter['sound']}"
                keyboard = [
                    [InlineKeyboardButton("🔁 Попробовать ещё", callback_data="quiz_script_sound")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
                reset_streak(user_id)
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # --- Письменная → буква / название ---
        if parts[1] == "script":
            scr_parts = data.split("_")
            sub_mode = scr_parts[2]  # "letter" / "name"
            answer_id = int(scr_parts[3])
            correct_id = context.user_data.get("script_correct_id")
            correct_letter = get_letter_by_id(correct_id)
            back_data = f"quiz_script_{sub_mode}"

            if answer_id == correct_id:
                mark_letter_learned(user_id, correct_id)
                add_points(user_id, 10)
                text = f"{get_motivation()} **{correct_letter['letter']}** — {correct_letter['name_ru']}!"
                keyboard = [
                    [InlineKeyboardButton("🔁 Ещё", callback_data=back_data)],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
            else:
                text = f"❌ Неверно. Правильный ответ: **{correct_letter['letter']}** — {correct_letter['name_ru']}"
                keyboard = [
                    [InlineKeyboardButton("🔁 Попробовать ещё", callback_data=back_data)],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
                reset_streak(user_id)
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if parts[1] == "sofit":
            answer = parts[2]
            correct = context.user_data.get("sofit_correct_char")
            letter_id = context.user_data.get("sofit_letter_id")

            if answer == correct:
                mark_letter_learned(user_id, letter_id)
                add_points(user_id, 10)
                text = f"{get_motivation()} Это **{correct}**!"
                keyboard = [
                    [InlineKeyboardButton("🔁 Ещё", callback_data="quiz_sofit")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
            else:
                text = f"❌ Неверно. Правильный ответ: {correct}"
                keyboard = [
                    [InlineKeyboardButton("🔁 Попробовать ещё", callback_data="quiz_sofit")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

        elif parts[1] == "sound":
            answer_sound = parts[2]
            correct_id = context.user_data.get("quiz_correct_id")
            correct_letter = get_letter_by_id(correct_id)
            correct_sounds = correct_letter["sound"].split("/") if correct_letter else []

            if answer_sound == correct_letter["sound"] or answer_sound in correct_sounds:
                mark_letter_learned(user_id, correct_id)
                add_points(user_id, 10)
                stats = get_stats(user_id)
                streak = stats["current_streak"] if stats else 0
                streak_msg = get_streak_message(streak)
                text = f"{get_motivation()} **{correct_letter['letter']}** — {correct_letter['name_ru']}!"
                if streak_msg:
                    text += f"\n\n{streak_msg}"
                keyboard = [
                    [InlineKeyboardButton("🔁 Ещё", callback_data="quiz_letter")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
            else:
                text = f"❌ Неверно. Правильный звук: {correct_letter['sound']}"
                keyboard = [
                    [InlineKeyboardButton("🔁 Попробовать ещё", callback_data="quiz_letter")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
                reset_streak(user_id)
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

        else:
            # Обычный ответ: ans_{id}
            try:
                answer_id = int(parts[1])
            except ValueError:
                return

            correct_id = context.user_data.get("quiz_correct_id")
            correct_letter = get_letter_by_id(correct_id)

            if answer_id == correct_id:
                mark_letter_learned(user_id, correct_id)
                add_points(user_id, 10)

                stats = get_stats(user_id)
                streak = stats["current_streak"] if stats else 0
                streak_msg = get_streak_message(streak)

                text = f"{get_motivation()} **{correct_letter['letter']}** — {correct_letter['name_ru']}!"
                if streak_msg:
                    text += f"\n\n{streak_msg}"

                keyboard = [
                    [InlineKeyboardButton("🔁 Ещё", callback_data="quiz_sound")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
            else:
                correct_answer = get_letter_by_id(correct_id)
                text = f"❌ Неверно. Правильный ответ: **{correct_answer['letter']}** — {correct_answer['name_ru']}"
                keyboard = [
                    [InlineKeyboardButton("🔁 Попробовать ещё", callback_data="quiz_sound")],
                    [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
                ]
                reset_streak(user_id)

            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    return


async def build_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("build_"):
        parts = data.split("_", 2)
        if parts[1] == "done":
            word_data = context.user_data.get("current_word")
            attempt = context.user_data.get("build_attempt", [])
            correct = context.user_data.get("build_letters", list(word_data["he"]))

            if attempt == correct:
                user_id = update.effective_user.id
                add_points(user_id, 20)
                text = f"{get_motivation()} **{word_data['he']}** — {word_data['ru']}!"
                for ch in correct:
                    letter = [l for l in get_all_letters() if l["letter"] == ch]
                    if letter:
                        mark_letter_learned(user_id, letter[0]["id"])
            else:
                text = f"❌ Не совсем. Было: **{word_data['he']}** — {word_data['ru']}"

            text += "\n\nПопробуешь ещё?"
            keyboard = [
                [InlineKeyboardButton("🔁 Новое слово", callback_data="menu_build")],
                [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # build_{index}_{letter}
        idx = int(parts[1])
        letter = parts[2]
        attempt = context.user_data.setdefault("build_attempt", [])
        attempt.append(letter)

        word_he = context.user_data.get("build_letters", [])
        remaining = len(word_he) - len(attempt)
        await query.edit_message_text(
            f"🔊 Собери слово!\n\n"
            f"Собрано: {' '.join(attempt)}\nОсталось букв: {remaining}\n\n"
            "Продолжай:",
            reply_markup=_build_keyboard(word_he, "build"),
        )

    return


async def scramble_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("scramble_"):
        parts = data.split("_", 2)
        if parts[1] == "done":
            word_data = context.user_data.get("scramble_word")
            attempt = context.user_data.get("scramble_attempt", [])
            correct = list(word_data["he"])

            if attempt == correct:
                user_id = update.effective_user.id
                add_points(user_id, 15)
                text = f"{get_motivation()} **{word_data['he']}** — {word_data['ru']}!"
            else:
                text = f"❌ Не совсем. Было: **{word_data['he']}** — {word_data['ru']}"

            text += "\n\nЕщё слово?"
            keyboard = [
                [InlineKeyboardButton("🌀 Ещё", callback_data="menu_scramble")],
                [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        idx = int(parts[1])
        letter = parts[2]
        attempt = context.user_data.setdefault("scramble_attempt", [])
        attempt.append(letter)

        remaining = context.user_data.get("scramble_letters", [])
        remaining = [l for i, l in enumerate(remaining) if i != idx]
        context.user_data["scramble_letters"] = remaining

        word_ru = context.user_data.get("scramble_word", {}).get("ru", "")
        await query.edit_message_text(
            f"🌀 **Перепутанные буквы**\n\n"
            f"Подсказка: {word_ru}\n\n"
            f"Собрано: {' '.join(attempt)}\nОсталось букв: {len(remaining)}",
            reply_markup=_build_keyboard(remaining, "scramble"),
        )

    return


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📚 **Hebrew Alphabet Bot**\n\n"
        "**Команды:**\n"
        "/start — Главное меню\n"
        "/help — Эта справка\n\n"
        "**Уровни:**\n"
        "🔤 Алфавит — звук→буква, буква→звук, соседи по алфавиту\n"
        "🔢 Сосчитай буквы — найди букву в строке\n"
        "🔊 Собери слово — по звуку\n\n"
        "Создано с ❤️ OpenCode + Ольга"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern=r"^(menu_|explore_)"))
    app.add_handler(CallbackQueryHandler(quiz_handler, pattern=r"^quiz_"))
    app.add_handler(CallbackQueryHandler(answer_handler, pattern=r"^ans_"))
    app.add_handler(CallbackQueryHandler(build_handler, pattern=r"^build_"))
    # app.add_handler(CallbackQueryHandler(scramble_handler, pattern=r"^scramble_"))  # временно отключено

    app.add_error_handler(error_handler)

    print("Бот запущен! Нажми Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
