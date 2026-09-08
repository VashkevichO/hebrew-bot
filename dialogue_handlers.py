"""Хендлеры диалогов и корней (недельный цикл, озвучка, перевод, каталог корней).

Callback-данные (все начинаются с dlg_ / root_ / menu_dialogues / menu_roots):
  menu_dialogues        — подменю диалогов
  dlg_week              — диалог текущей недели
  dlg_random            — случайный диалог
  dlg_audio_<did>_<idx> — озвучить idx-ю реплику (первый вариант)
  dlg_tr_<did>          — показать/скрыть перевод
  dlg_done_<did>        — отметить диалог (full/partial)
  menu_roots            — каталог корней (страница 0)
  roots_page_<n>        — страница каталога n
  root_show_<letters>   — карточка корня (letters — буквы корня, напр. שלמ)
"""
import asyncio
import random

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from utils.database import collect_dialogue, get_dialogue_status
from utils.dialogues import (
    load_dialogues,
    get_dialogue_by_id,
    get_dialogue_for_date,
    get_week_info,
)
from utils.roots import (
    load_roots,
    root_letters,
    find_roots_in_dialogue,
    find_root_by_query,
)
from utils.tts import generate_audio

PAGE_SIZE = 10

WHO_LABEL = {"a": "A", "b": "B"}


# ===== Вспомогательное =====

async def _send_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, audio_path):
    """Отправляет голосовое, удалив предыдущее голосовое в этой сессии."""
    chat_id = update.effective_chat.id
    last = context.user_data.pop("dlg_last_voice_id", None)
    if last:
        try:
            await context.bot.delete_message(chat_id, last)
        except Exception:
            pass
    with open(audio_path, "rb") as f:
        msg = await context.bot.send_voice(chat_id, f)
    context.user_data["dlg_last_voice_id"] = msg.message_id


def _format_dialogue(dlg, label, state):
    """Текст диалога: роли, варианты, перевод если включён."""
    lines = [f"🎭 {dlg['title_ru']}", f"{label}"]
    played = set(state.get("played", []))
    total = len(dlg["lines"])
    if played:
        lines.append(f"🔊 Прослушано: {len(played)} из {total}")
    lines.append("")

    for i, line in enumerate(dlg["lines"]):
        who = WHO_LABEL[line["who"]]
        main = line["variants"][0]
        mark = "☑️ " if i in played else ""
        lines.append(f"{who}: {mark}{main['he']}")
        for extra in line["variants"][1:]:
            note = f" — {extra['note']}" if extra.get("note") else ""
            lines.append(f"    · {extra['he']}{note}")
        if state.get("tr"):
            lines.append(f"    📖 {line['ru']}")
    return "\n".join(lines)


def _dialogue_keyboard(dlg, state, with_random=True):
    """Клавиатура диалога: ▶, перевод, готово, корни, навигация."""
    kb = []
    # озвучка реплик
    line_btns = [
        InlineKeyboardButton(f"▶{i + 1}", callback_data=f"dlg_audio_{dlg['id']}_{i}")
        for i in range(len(dlg["lines"]))
    ]
    kb.append(line_btns)

    # перевод + готово
    tr_label = "🇷🇺 Скрыть перевод" if state.get("tr") else "🇷🇺 Показать перевод"
    kb.append([
        InlineKeyboardButton(tr_label, callback_data=f"dlg_tr_{dlg['id']}"),
        InlineKeyboardButton("✅ Готово", callback_data=f"dlg_done_{dlg['id']}"),
    ])

    # корни в диалоге
    found = find_roots_in_dialogue(dlg)
    if found:
        root_btns = [
            InlineKeyboardButton(
                f"🌱 {r['root']}", callback_data=f"dlg_root_{dlg['id']}_{root_letters(r['root'])}"
            )
            for r in found[:6]
        ]
        kb.append(root_btns)

    # навигация
    nav = [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")]
    if with_random:
        nav.insert(0, InlineKeyboardButton("🎲 Случайный", callback_data="dlg_random"))
    kb.append(nav)
    return InlineKeyboardMarkup(kb)


def _get_state(context, did):
    st = context.user_data.get("dlg_state")
    if not st or st.get("did") != did:
        st = {"did": did, "played": [], "tr": False}
        context.user_data["dlg_state"] = st
    return st


async def _show_dialogue(update, context, dlg, label, with_random=True, as_command=False):
    """Показывает диалог: новым сообщением (команда) или правкой текущего."""
    state = _get_state(context, dlg["id"])
    state["_label"] = label
    text = _format_dialogue(dlg, label, state)
    kb = _dialogue_keyboard(dlg, state, with_random)

    if as_command:
        await update.message.reply_text(text, reply_markup=kb)
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, reply_markup=kb)


# ===== Команды =====

async def cmd_dialogue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/dialogue — случайный диалог."""
    dlg = random.choice(load_dialogues())
    await _show_dialogue(update, context, dlg, "🎲 Случайный диалог", as_command=True)


async def cmd_dialogue_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/dialogue_today — диалог текущей недели."""
    dlg, info = get_dialogue_for_date()
    total = len(load_dialogues())
    label = f"🗓 Неделя {info['week'] + 1} · диалог {info['index'] + 1} из {total}"
    await _show_dialogue(update, context, dlg, label, with_random=True, as_command=True)


async def cmd_root(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/root [корень|слово] — карточка корня. Без аргумента — случайный корень."""
    query_text = " ".join(context.args).strip()
    roots = load_roots()

    if query_text:
        root = find_root_by_query(query_text)
        if not root:
            await update.message.reply_text(
                f"🤷 Не нашёл корень или слово «{query_text}».\n"
                "Попробуй: /root שלום или открой 📚 Каталог корней.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📚 Все корни", callback_data="menu_roots"),
                ]]),
            )
            return
    else:
        root = random.choice(roots)

    await _send_root_card(update, context, root, as_command=True)


# ===== Колбэки =====

async def dialogue_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    # --- раздел «Диалоги»: сразу показываем диалог недели ---
    if data in ("menu_dialogues", "dlg_week"):
        dlg, info = get_dialogue_for_date()
        total = len(load_dialogues())
        label = f"🗓 Неделя {info['week'] + 1} · диалог {info['index'] + 1} из {total}"
        await _show_dialogue(update, context, dlg, label, with_random=True)
        return

    if data == "dlg_random":
        dlg = random.choice(load_dialogues())
        await _show_dialogue(update, context, dlg, "🎲 Случайный диалог", with_random=True)
        return

    # --- озвучка реплики ---
    if data.startswith("dlg_audio_"):
        await query.answer()
        _, _, did, idx = data.split("_", 3)
        idx = int(idx)
        dlg = get_dialogue_by_id(did)
        if not dlg or idx >= len(dlg["lines"]):
            return
        state = _get_state(context, did)
        if idx not in state["played"]:
            state["played"].append(idx)
        line = dlg["lines"][idx]
        variant = line["variants"][0]
        text = variant.get("tts") or variant["he"]
        try:
            path = await generate_audio(text)
            await _send_voice(update, context, path)
        except Exception as e:
            await query.message.reply_text(f"Не удалось озвучить: {e}")
        # обновляем галочки в сообщении
        rendered = _format_dialogue(dlg, state.get("_label", ""), state)
        try:
            await query.edit_message_text(rendered, reply_markup=_dialogue_keyboard(dlg, state))
        except Exception:
            pass
        return

    # --- перевод ---
    if data.startswith("dlg_tr_"):
        await query.answer()
        did = data.split("_", 2)[2]
        state = _get_state(context, did)
        state["tr"] = not state.get("tr", False)
        dlg = get_dialogue_by_id(did)
        if dlg:
            label = state.get("_label", "")
            await query.edit_message_text(
                _format_dialogue(dlg, label, state),
                reply_markup=_dialogue_keyboard(dlg, state),
            )
        return

    # --- готово (засчитывание) ---
    if data.startswith("dlg_done_"):
        await query.answer()
        did = data.split("_", 2)[2]
        dlg = get_dialogue_by_id(did)
        if not dlg:
            return
        state = _get_state(context, did)
        total = len(dlg["lines"])
        played_all = len(state.get("played", [])) >= total
        status = "full" if played_all else "partial"

        res = collect_dialogue(user_id, did, status)
        existing = get_dialogue_status(user_id, did)

        if res is None and existing == "full":
            msg = f"✅ «{dlg['title_ru']}» уже собран полностью!"
        elif status == "full":
            msg = f"✅ «{dlg['title_ru']}» собран полностью!"
        else:
            left = total - len(state.get("played", []))
            msg = (
                f"◐ «{dlg['title_ru']}» отмечен.\n"
                f"Осталось непрослушанных реплик: {left}.\n"
                "Прослушай все (▶) и нажми «Готово» ещё раз — станет ✅."
            )
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎲 Случайный", callback_data="dlg_random"),
                 InlineKeyboardButton("🗓 Недели", callback_data="dlg_week")],
                [InlineKeyboardButton("🔙 В меню", callback_data="menu_main")],
            ]),
        )
        return

    # --- каталог корней ---
    if data == "menu_roots":
        await _show_roots_page(update, context, 0)
        return

    if data.startswith("roots_page_"):
        page = int(data.split("_")[2])
        await _show_roots_page(update, context, page)
        return

    # --- карточка корня из диалога (с возвратом) ---
    if data.startswith("dlg_root_"):
        await query.answer()
        rest = data[len("dlg_root_"):]
        did, letters = rest.split("_", 1)
        root = find_root_by_query(letters)
        if root:
            await _send_root_card(update, context, root, back_cb=f"dlg_open_{did}")
        return

    # --- карточка корня из каталога (с возвратом на страницу) ---
    if data.startswith("cat_root_"):
        await query.answer()
        rest = data[len("cat_root_"):]
        page, letters = rest.split("_", 1)
        root = find_root_by_query(letters)
        if root:
            await _send_root_card(update, context, root, back_cb=f"roots_page_{page}")
        return

    # --- возврат к диалогу из карточки корня ---
    if data.startswith("dlg_open_"):
        did = data[len("dlg_open_"):]
        dlg = get_dialogue_by_id(did)
        if dlg:
            state = _get_state(context, did)
            label = state.get("_label", "")
            await _show_dialogue(update, context, dlg, label, with_random=True)
        return

    # --- карточка корня (фолбэк) ---
    if data.startswith("root_show_"):
        await query.answer()
        letters = data.split("_", 2)[2]
        root = find_root_by_query(letters)
        if root:
            await _send_root_card(update, context, root)
        return


async def _show_roots_page(update, context, page):
    """Каталог корней с пагинацией."""
    roots = load_roots()
    total = len(roots)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    start = page * PAGE_SIZE
    chunk = roots[start:start + PAGE_SIZE]

    query = update.callback_query
    await query.answer()

    lines = [f"🌱 **Корни иврита** · {start + 1}–{start + len(chunk)} из {total}", ""]
    for r in chunk:
        words_sample = ", ".join(w["he"] for w in r["words"][:2])
        lines.append(f"• **{r['root']}** — {r['meaning']}")
        lines.append(f"  {words_sample}")
    lines.append("")
    lines.append("Корень — это «каркас» слова. Нажми на корень, чтобы увидеть слова.")

    # кнопки корней
    kb = []
    row = []
    for r in chunk:
        row.append(InlineKeyboardButton(
            r["root"], callback_data=f"cat_root_{page}_{root_letters(r['root'])}"
        ))
        if len(row) == 3:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    # пагинация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Назад", callback_data=f"roots_page_{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{pages}", callback_data="roots_page_0"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("Вперёд ▶", callback_data=f"roots_page_{page + 1}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton("🔙 В меню", callback_data="menu_main")])

    await query.edit_message_text(
        "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )


async def _send_root_card(update, context, root, as_command=False, back_cb=None):
    """Карточка корня: значение, слова, кнопки назад/каталог/собери слово."""
    lines = [f"🌱 **Корень: {root['root']}**", f"📖 {root['meaning']}", ""]
    for i, w in enumerate(root["words"], start=1):
        lines.append(f"{i}. **{w['he']}** — {w['ru']}")
    lines.append("")
    lines.append("💡 Многие слова иврита собраны из трёх букв корня.")

    btns = []
    if back_cb:
        btns.append(InlineKeyboardButton("🔙 Назад", callback_data=back_cb))
    btns.append(InlineKeyboardButton("📚 Все корни", callback_data="menu_roots"))
    kb = InlineKeyboardMarkup([
        btns,
        [InlineKeyboardButton("🔊 Собери слово", callback_data="menu_build")],
    ])

    if as_command:
        await update.message.reply_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
    else:
        query = update.callback_query
        await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
