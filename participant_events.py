import sqlite3
from pathlib import Path

from aiogram import Router
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

DB_PATH = Path(__file__).resolve().parent / "data.db"
router = Router()

participant_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Ивенты, в которых я участвую")],
        [KeyboardButton(text="Все ивенты")],
    ],
    resize_keyboard=True,
)


def get_future_events(limit: int | None = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = """
        SELECT event_id, name, description, price, address,
               max_participants, event_date, event_time
        FROM events
        WHERE is_deleted = 0
          AND date(event_date) >= date('now')
        ORDER BY event_date, event_time
    """
    if limit:
        query += " LIMIT ?"
        cursor.execute(query, (limit,))
    else:
        cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_user_events(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT e.event_id, e.name, e.description, e.price, e.address,
               e.max_participants, e.event_date, e.event_time
        FROM events e
        JOIN registrations r ON r.event_id = e.event_id
        WHERE r.user_id = ?
          AND e.is_deleted = 0
          AND date(e.event_date) >= date('now')
        ORDER BY e.event_date, e.event_time
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def count_event_registrations(event_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM registrations WHERE event_id = ?",
        (event_id,),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def is_user_registered(event_id: int, user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM registrations WHERE event_id = ? AND user_id = ? LIMIT 1",
        (event_id, user_id),
    )
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def register_user_for_event(event_id: int, user_id: int, user_name: str, user_nickname: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM events WHERE event_id = ?",
        (event_id,),
    )
    row = cursor.fetchone()
    event_name = row[0] if row else ""
    cursor.execute(
        """
        INSERT INTO registrations (event_id, user_id, event_name, user_name, user_nickname)
        VALUES (?, ?, ?, ?, ?)
        """,
        (event_id, user_id, event_name, user_name, user_nickname),
    )
    conn.commit()
    conn.close()


def cancel_user_registration(event_id: int, user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM registrations WHERE event_id = ? AND user_id = ?",
        (event_id, user_id),
    )
    conn.commit()
    conn.close()


def format_event_text(event_row, is_full: bool) -> str:
    event_id, name, desc, price, address, _, date_str, time_str = event_row
    warning = "\n⚠️ Мест нет" if is_full else ""
    return (
        f"🎬 <b>{name}</b>\n"
        f"📝 {desc}\n\n"
        f"💰 Цена: {price}\n"
        f"🏠 Адрес: {address}\n"
        f"📅 {date_str} ⏰ {time_str}"
        f"{warning}"
    )


def build_event_keyboard(event_id: int, user_id: int, is_full: bool) -> InlineKeyboardMarkup | None:
    if is_user_registered(event_id, user_id):
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отменить регистрацию", callback_data=f"user_cancel:{event_id}")]]
        )
    if is_full:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Записаться", callback_data=f"user_register:{event_id}")]]
    )


def get_event_by_id(event_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT event_id, name, description, price, address,
               max_participants, event_date, event_time
        FROM events
        WHERE event_id = ? AND is_deleted = 0
        """,
        (event_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def build_event_card(event_row, user_id: int):
    event_id = event_row[0]
    max_participants = event_row[5]
    registered_count = count_event_registrations(event_id)
    is_full = max_participants is not None and registered_count >= max_participants
    text = format_event_text(event_row, is_full=is_full)
    keyboard = build_event_keyboard(event_id, user_id, is_full=is_full)
    return text, keyboard


async def send_nearest_event(message: Message):
    events = get_future_events(limit=1)
    if not events:
        await message.answer("📭 Будущих ивентов пока нет.", reply_markup=participant_menu)
        return

    event_row = events[0]
    text, keyboard = build_event_card(event_row, message.from_user.id)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await message.answer("Выберите, что хотите посмотреть:", reply_markup=participant_menu)


@router.message(lambda msg: msg.text == "Все ивенты")
async def show_all_events(message: Message):
    events = get_future_events()
    if not events:
        await message.answer("📭 Будущих ивентов пока нет.")
        return

    for event_row in events:
        text, keyboard = build_event_card(event_row, message.from_user.id)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(lambda msg: msg.text == "Ивенты, в которых я участвую")
async def show_user_events(message: Message):
    events = get_user_events(message.from_user.id)
    if not events:
        await message.answer("📭 Пока нет ивентов, в которых вы участвуете.")
        return

    for event_row in events:
        text, keyboard = build_event_card(event_row, message.from_user.id)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(lambda c: c.data.startswith("user_register:"))
async def user_register(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    event_row = get_event_by_id(event_id)
    if not event_row:
        await call.answer("Ивент не найден", show_alert=True)
        return

    max_participants = event_row[5]
    registered_count = count_event_registrations(event_id)
    is_full = max_participants is not None and registered_count >= max_participants
    if is_full:
        text = format_event_text(event_row, is_full=True)
        keyboard = build_event_keyboard(event_id, call.from_user.id, is_full=True)
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await call.answer("Мест нет")
        return

    if not is_user_registered(event_id, call.from_user.id):
        user_name = call.from_user.full_name
        user_nickname = call.from_user.username or ""
        register_user_for_event(event_id, call.from_user.id, user_name, user_nickname)

    text, keyboard = build_event_card(event_row, call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer("Записано")


@router.callback_query(lambda c: c.data.startswith("user_cancel:"))
async def user_cancel(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    cancel_user_registration(event_id, call.from_user.id)
    event_row = get_event_by_id(event_id)
    if not event_row:
        await call.answer("Ивент не найден", show_alert=True)
        return

    text, keyboard = build_event_card(event_row, call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer("Регистрация отменена")
