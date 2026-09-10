"""Тренировки: «Глаголы» (спряжение) и «Собери предложение».

Callback-данные:
  menu_verbs / menu_sentence — вход в модуль (вводный экран при первом заходе)
  vrb_start   — начать сессию глаголов (5 вопросов)
  vrb_ans_<i> — ответ: i = индекс варианта
  vrb_next    — следующий вопрос / итог
  vrb_hint    — справка «настоящее время»
  vrb_resume  — вернуться к вопросу после подсказки
  vrb_again   — повторить сессию
  sent_start / sent_add_<i> / sent_undo / sent_check /
  sent_next / sent_retry / sent_reveal / sent_hint / sent_resume
"""
import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from utils import sentences as sentences_lib
from utils import verbs as verbs_lib
from utils.database import add_points, get_intro_seen, mark_intro_seen
from utils.tts import generate_audio


async def _send_voice(update, context, audio_path):
    """Отправляет голосовое (удаляя предыдущее в этой сессии)."""
    chat_id = update.effective_chat.id
    last = context.user_data.pop("vrb_last_voice_id", None)
    if last:
        try:
            await context.bot.delete_message(chat_id, last)
        except Exception:
            pass
    with open(audio_path, "rb") as f:
        msg = await context.bot.send_voice(chat_id, f)
    context.user_data["vrb_last_voice_id"] = msg.message_id

VERB_QUESTIONS = 5
SENTENCE_POINTS = 15

BINYAN_NAMES = {
    "paal": "пааль (простое действие)",
    "piel": "пиэль (интенсив, доведение до результата)",
    "hifil": "хифиль (причина, побуждение)",
}


def _menu_kb(extra_rows, back_cb="menu_main"):
    rows = [list(r) for r in extra_rows]
    rows.append([InlineKeyboardButton("🔙 В меню", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


def render_verb_card_text(verb):
    """Текст карточки глагола (используется из карточки корня)."""
    p = verb["present"]
    binyan = BINYAN_NAMES.get(verb.get("binyan"), verb.get("binyan", ""))
    lines = [
        f"🏛 **Глагол: {verb['infinitive']}**",
        f"📖 {verb['meaning']}",
        f"🌱 Корень: {verb['root']}",
        f"🔧 {binyan}",
        "",
        "**Настоящее время:**",
        f"👨 он: {p['male_sg']}   👩 она: {p['female_sg']}",
        f"👬 они (м.): {p['male_pl']}   👭 они (ж.): {p['female_pl']}",
    ]
    if verb.get("examples"):
        ex = verb["examples"][0]
        lines.append("")
        lines.append(f"💬 {ex['he']} — _{ex['ru']}_")
    return "\n".join(lines)


# ===== Вводные экраны =====

VERB_INTRO_TEXT = (
    "🏛 **Глаголы**\n\n"
    "Глаголы — это сердце языка. В иврите они строятся из **корней** "
    "(ты уже видел их в разделе «Слова и корни»). Корень + биньян "
    "(пааль, пиэль, хифиль) дают значение.\n\n"
    "Здесь ты потренируешься спрягать глаголы в **настоящем времени**: "
    "по родам и числам.\n\n"
    "📖 Если что-то непонятно — жми «ℹ️ Подсказка» во время тренировки."
)

SENTENCE_INTRO_TEXT = (
    "🧩 **Собери предложение**\n\n"
    "В иврите базовый порядок слов: **кто + что делает + что / где**. "
    "Подлежащее — имя или местоимение, к нему глагол в нужной форме.\n\n"
    "Тебе дан перевод на русский — собери предложение из слов-кнопок. "
    "⚠️ Внимание: среди слов есть **лишние**!\n\n"
    "📖 О порядке слов — «Справка» → «Порядок слов»."
)


async def _show_intro_or_start(update, context, intro_key, intro_text, start_cb):
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()

    if not get_intro_seen(user_id, intro_key):
        mark_intro_seen(user_id, intro_key)
        kb = _menu_kb([[InlineKeyboardButton("▶ Начать", callback_data=start_cb)]])
        await query.edit_message_text(intro_text, reply_markup=kb, parse_mode="Markdown")
    else:
        # сразу запускаем модуль
        if start_cb == "vrb_start":
            await _start_verbs(update, context)
        else:
            await _start_sentence(update, context)


# ===== ГЛАГОЛЫ =====

async def _start_verbs(update, context):
    context.user_data["vrb"] = {
        "total": VERB_QUESTIONS,
        "answered": 0,
        "correct": 0,
        "last_q": None,
        "last_ok": None,
    }
    await _next_verb_question(update, context)


def _verb_question_kb(session):
    q = session["last_q"]
    rows = []
    # варианты по 2 в ряд
    opts = q["options"]
    pairs = [opts[i:i + 2] for i in range(0, len(opts), 2)]
    for pair in pairs:
        row = []
        for opt in pair:
            idx = q["options"].index(opt)
            row.append(InlineKeyboardButton(opt, callback_data=f"vrb_ans_{idx}"))
        rows.append(row)
    rows.append([
        InlineKeyboardButton("⏹ Выйти", callback_data="menu_main"),
    ])
    return InlineKeyboardMarkup(rows)


def _verb_question_text(q, session):
    verb = q["verb"]
    return (
        f"🏛 **Спряжение глагола**  ({session['answered'] + 1}/{session['total']})\n\n"
        f"Глагол: **{verb['infinitive']}** — {verb['meaning']}\n"
        f"Местоимение: **{q['pronoun_he']}** ({q['pronoun_ru']})\n\n"
        "Выбери правильную форму:"
    )


async def _render_verb_question(update, context):
    query = update.callback_query
    session = context.user_data["vrb"]
    q = session["last_q"]
    await query.edit_message_text(
        _verb_question_text(q, session),
        reply_markup=_verb_question_kb(session),
        parse_mode="Markdown",
    )


async def _next_verb_question(update, context):
    session = context.user_data["vrb"]
    if session["answered"] >= session["total"]:
        await _verb_finish(update, context)
        return
    session["last_q"] = verbs_lib.build_question()
    session["last_ok"] = None
    await _render_verb_question(update, context)


async def _verb_finish(update, context):
    query = update.callback_query
    session = context.user_data["vrb"]
    total = session["total"]
    correct = session["correct"]
    text = (
        f"🏁 **Тренировка окончена!**\n\n"
        f"Правильных ответов: **{correct} из {total}**"
    )
    if correct == total:
        text += "\n\n🎉 Отлично, всё верно!"
    elif correct >= total // 2:
        text += "\n\n💪 Хорошо! Ещё немного — и будет идеально."
    else:
        text += "\n\n📖 Загляни в «Справку» → «Настоящее время» и попробуй ещё раз."
    kb = _menu_kb([
        [InlineKeyboardButton("🔁 Ещё раз", callback_data="vrb_start")],
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


async def _verb_answer(update, context, answer_idx):
    query = update.callback_query
    session = context.user_data.get("vrb")
    if not session or not session.get("last_q"):
        await query.answer("Начни тренировку заново")
        return
    q = session["last_q"]
    user_id = update.effective_user.id

    if answer_idx == q["correct_index"]:
        session["correct"] += 1
        session["last_ok"] = True
        add_points(user_id, 10)
        explanation = verbs_lib.explain_answer(q["pronoun_he"], q["correct"])
        text = (
            f"✅ **Верно!** «{q['correct']}» — правильная форма.\n\n"
            f"💡 {explanation}"
        )
    else:
        session["last_ok"] = False
        explanation = verbs_lib.explain_answer(q["pronoun_he"], q["correct"])
        text = (
            f"❌ Неверно.\nПравильно: **«{q['correct']}»**.\n\n"
            f"💡 {explanation}"
        )
    session["answered"] += 1

    kb = _menu_kb([[InlineKeyboardButton("▶ Дальше", callback_data="vrb_next")]])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


# ===== СОБЕРИ ПРЕДЛОЖЕНИЕ =====

async def _start_sentence(update, context):
    ex = sentences_lib.random_exercise()
    context.user_data["sent"] = {
        "ex": ex,
        "available": sentences_lib.shuffled_words(ex),
        "selected": [],
    }
    await _render_sentence(update, context)


def _sentence_kb(session, with_actions=True):
    ex = session["ex"]
    rows = []
    # слова-кнопки по 3 в ряд
    avail = session["available"]
    for i in range(0, len(avail), 3):
        row = [
            InlineKeyboardButton(w, callback_data=f"sent_add_{i + j}")
            for j, w in enumerate(avail[i:i + 3])
        ]
        rows.append(row)

    if with_actions:
        actions = [InlineKeyboardButton("↩️ Отменить", callback_data="sent_undo")]
        if session["selected"]:
            actions.append(InlineKeyboardButton("✅ Проверить", callback_data="sent_check"))
        rows.append(actions)
        rows.append([
            InlineKeyboardButton("⏭ Пропустить", callback_data="sent_next"),
            InlineKeyboardButton("🔙 В меню", callback_data="menu_main"),
        ])
    return InlineKeyboardMarkup(rows)


async def _render_sentence(update, context, edit=True):
    query = update.callback_query
    session = context.user_data["sent"]
    ex = session["ex"]
    selected = session["selected"]

    lines = [
        "🧩 **Собери предложение**",
        f"Перевод: «{ex['ru_translation']}»",
        "",
    ]
    if selected:
        lines.append(f"Ваше предложение: **{' '.join(selected)}**")
    else:
        lines.append("Ваше предложение: _нажимай слова по порядку_")
    lines.append("")
    lines.append("⚠️ Среди слов есть лишние!")

    if edit:
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=_sentence_kb(session),
            parse_mode="Markdown",
        )


async def _sentence_add(update, context, idx):
    query = update.callback_query
    session = context.user_data.get("sent")
    if not session:
        return
    avail = session["available"]
    if 0 <= idx < len(avail):
        word = avail.pop(idx)
        session["selected"].append(word)
    await _render_sentence(update, context)


async def _sentence_undo(update, context):
    query = update.callback_query
    session = context.user_data.get("sent")
    if not session:
        return
    if session["selected"]:
        word = session["selected"].pop()
        session["available"].insert(random.randint(0, len(session["available"])), word)
    await _render_sentence(update, context)


async def _sentence_check(update, context):
    query = update.callback_query
    session = context.user_data.get("sent")
    if not session or not session["selected"]:
        return
    user_id = update.effective_user.id
    result = sentences_lib.check_sentence(session["ex"], session["selected"])

    if result["ok"]:
        add_points(user_id, SENTENCE_POINTS)
        # озвучка собранного предложения
        sentence_he = " ".join(session["selected"])
        try:
            path = await generate_audio(sentence_he)
            await _send_voice(update, context, path)
        except Exception:
            pass
        text = (
            f"✅ **Правильно!** +{SENTENCE_POINTS} очков\n\n"
            f"💬 **{sentence_he}**"
        )
        kb = _menu_kb([
            [InlineKeyboardButton("▶ Ещё предложение", callback_data="sent_next"),
             InlineKeyboardButton("🔁 Это же", callback_data="sent_start")],
        ])
    else:
        text = f"❌ **Не совсем.**\n\n{result['text']}"
        kb = _menu_kb([
            [InlineKeyboardButton("🔁 Ещё попытка", callback_data="sent_retry")],
            [InlineKeyboardButton("👁 Показать ответ", callback_data="sent_reveal")],
            [InlineKeyboardButton("⏭ Следующее", callback_data="sent_next")],
        ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


async def _sentence_retry(update, context):
    session = context.user_data.get("sent")
    if session:
        session["available"] = sentences_lib.shuffled_words(session["ex"])
        session["selected"] = []
    await _render_sentence(update, context)


async def _sentence_reveal(update, context):
    query = update.callback_query
    session = context.user_data.get("sent")
    if not session:
        return
    ex = session["ex"]
    answer = " ".join(ex["correct_patterns"][0])
    text = f"👁 Правильное предложение:\n\n**{answer}**\n\n_{ex['ru_translation']}_"
    kb = _menu_kb([
        [InlineKeyboardButton("▶ Ещё предложение", callback_data="sent_next")],
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


async def _sentence_next(update, context):
    query = update.callback_query
    ex = sentences_lib.random_exercise()
    context.user_data["sent"] = {
        "ex": ex,
        "available": sentences_lib.shuffled_words(ex),
        "selected": [],
    }
    await _render_sentence(update, context)


# ===== Диспетчер =====

async def training_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data

    # --- карточка глагола из корня ---
    if data.startswith("gvb_"):
        await update.callback_query.answer()
        letters = data.split("_", 1)[1]
        verbs = verbs_lib.find_verbs_by_root_letters(letters)
        if verbs:
            verb = verbs[0]
            text = render_verb_card_text(verb)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔊 Озвучить инфинитив", callback_data=f"vrb_audio_{letters}")],
                [InlineKeyboardButton("🌱 К корню", callback_data=f"root_show_{letters}")],
                [InlineKeyboardButton("🏛 Тренировать глаголы", callback_data="menu_verbs"),
                 InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
            ])
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # --- озвучка инфинитива ---
    if data.startswith("vrb_audio_"):
        await update.callback_query.answer()
        letters = data.split("_", 2)[2]
        verbs = verbs_lib.find_verbs_by_root_letters(letters)
        if verbs:
            try:
                path = await generate_audio(verbs[0]["infinitive"])
                await _send_voice(update, context, path)
            except Exception as e:
                await update.callback_query.message.reply_text(f"Не удалось озвучить: {e}")
        return

    # --- вход в модули (с вводным экраном) ---
    if data == "menu_verbs":
        await _show_intro_or_start(update, context, "verbs_intro", VERB_INTRO_TEXT, "vrb_start")
        return
    if data == "menu_sentence":
        await _show_intro_or_start(update, context, "sentence_intro", SENTENCE_INTRO_TEXT, "sent_start")
        return

    # --- глаголы ---
    if data == "vrb_start":
        await update.callback_query.answer()
        await _start_verbs(update, context)
        return
    if data.startswith("vrb_ans_"):
        await update.callback_query.answer()
        idx = int(data.split("_")[2])
        await _verb_answer(update, context, idx)
        return
    if data == "vrb_next":
        await update.callback_query.answer()
        await _next_verb_question(update, context)
        return

    # --- предложения ---
    if data == "sent_start":
        await update.callback_query.answer()
        await _start_sentence(update, context)
        return
    if data.startswith("sent_add_"):
        await update.callback_query.answer()
        idx = int(data.split("_")[2])
        await _sentence_add(update, context, idx)
        return
    if data == "sent_undo":
        await update.callback_query.answer()
        await _sentence_undo(update, context)
        return
    if data == "sent_check":
        await update.callback_query.answer()
        await _sentence_check(update, context)
        return
    if data == "sent_next":
        await update.callback_query.answer()
        await _sentence_next(update, context)
        return
    if data == "sent_retry":
        await update.callback_query.answer()
        await _sentence_retry(update, context)
        return
    if data == "sent_reveal":
        await update.callback_query.answer()
        await _sentence_reveal(update, context)
        return
