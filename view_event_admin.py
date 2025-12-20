import sqlite3
from pathlib import Path
from datetime import datetime

from aiogram import Router
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

DB_PATH = Path(__file__).resolve().parent / "data.db"
router = Router()

# --------------------------------------------------
# FSM для редактирования одного поля
# --------------------------------------------------

class EditEventState(StatesGroup):
    value = State()


# --------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------

def get_future_events():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_id, name, description, price, address,
               max_participants, event_date, event_time
        FROM events
        WHERE is_deleted = 0
          AND date(event_date) >= date('now')
        ORDER BY event_date, event_time
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_event(event_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_id, name, description, price, address,
               max_participants, event_date, event_time
        FROM events
        WHERE event_id = ? AND is_deleted = 0
    """, (event_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def update_event_field(event_id: int, field: str, value):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE events SET {field} = ? WHERE event_id = ?",
        (value, event_id)
    )
    conn.commit()
    conn.close()


def mark_event_deleted(event_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE events SET is_deleted = 1 WHERE event_id = ?",
        (event_id,)
    )
    conn.commit()
    conn.close()


def get_event_participants(event_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_name, user_nick
        FROM event_participants
        WHERE event_id = ?
    """, (event_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


# --------------------------------------------------
# Клавиатуры
# --------------------------------------------------

def event_main_kb(event_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"event_edit:{event_id}")],
        [InlineKeyboardButton(text="👥 Просмотреть участников", callback_data=f"event_users:{event_id}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"event_delete:{event_id}")]
    ])


def event_edit_kb(event_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад", callback_data=f"event_back:{event_id}")],
        [InlineKeyboardButton(text="🎬 Название", callback_data=f"event_edit_name:{event_id}")],
        [InlineKeyboardButton(text="📝 Описание", callback_data=f"event_edit_description:{event_id}")],
        [InlineKeyboardButton(text="💰 Цена", callback_data=f"event_edit_price:{event_id}")],
        [InlineKeyboardButton(text="🏠 Адрес", callback_data=f"event_edit_address:{event_id}")],
        [InlineKeyboardButton(text="👥 Макс. участников", callback_data=f"event_edit_max:{event_id}")],
        [InlineKeyboardButton(text="📅 Дата", callback_data=f"event_edit_date:{event_id}")],
        [InlineKeyboardButton(text="⏰ Время", callback_data=f"event_edit_time:{event_id}")]
    ])


def delete_confirm_kb(event_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data=f"event_delete_yes:{event_id}")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"event_delete_no:{event_id}")]
    ])


# --------------------------------------------------
# Показ списка будущих ивентов
# --------------------------------------------------

async def show_future_events(message: Message):
    events = get_future_events()

    if not events:
        await message.answer("📭 Будущих ивентов пока нет.")
        return

    for e in events:
        event_id, name, desc, price, address, max_p, date, time = e

        text = (
            f"🎬 <b>{name}</b>\n"
            f"📝 {desc}\n\n"
            f"💰 Цена: {price}\n"
            f"🏠 Адрес: {address}\n"
            f"👥 Макс: {max_p}\n"
            f"📅 {date} ⏰ {time}"
        )

        await message.answer(
            text,
            reply_markup=event_main_kb(event_id),
            parse_mode="HTML"
        )


# --------------------------------------------------
# Callback-хендлеры
# --------------------------------------------------

@router.callback_query(lambda c: c.data.startswith("event_edit:"))
async def event_edit(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    await call.message.edit_reply_markup(event_edit_kb(event_id))


@router.callback_query(lambda c: c.data.startswith("event_back:"))
async def event_back(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    await call.message.edit_reply_markup(event_main_kb(event_id))


@router.callback_query(lambda c: c.data.startswith("event_users:"))
async def event_users(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    users = get_event_participants(event_id)

    if not users:
        text = "👥 Участников пока нет."
    else:
        lines = [f"• {u[0]} ({u[1]})" for u in users]
        text = "👥 Участники:\n" + "\n".join(lines)

    await call.message.answer(text)


@router.callback_query(lambda c: c.data.startswith("event_delete:"))
async def event_delete(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    await call.message.answer(
        "⚠️ Ты уверен, что хочешь удалить этот ивент?",
        reply_markup=delete_confirm_kb(event_id)
    )


@router.callback_query(lambda c: c.data.startswith("event_delete_yes:"))
async def event_delete_yes(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    mark_event_deleted(event_id)
    await call.message.answer("🗑 Ивент удалён.")


@router.callback_query(lambda c: c.data.startswith("event_delete_no:"))
async def event_delete_no(call: CallbackQuery):
    await call.message.answer("❎ Удаление отменено.")
