import sqlite3
from pathlib import Path
from datetime import datetime

from aiogram import Router
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BufferedInputFile,
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from ics_utils import build_event_ics
DB_PATH = Path(__file__).resolve().parent / "data.db"
router = Router()

EDIT_FIELDS = {
    "name": ("Название", "name"),
    "description": ("Описание", "description"),
    "price": ("Цену", "price"),
    "address": ("Адрес", "address"),
    "max": ("максимальное количество участников", "max_participants"),
    "date": ("дату (DD.MM)", "event_date"),
    "time": ("время (HH:MM)", "event_time"),
}



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
        SELECT user_name, user_nickname
        FROM registrations
        WHERE event_id = ?
    """, (event_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def count_event_registrations(event_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM registrations WHERE event_id = ?",
        (event_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count



# --------------------------------------------------
# Клавиатуры
# --------------------------------------------------

def event_main_kb(event_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"event_edit:{event_id}")],
        [InlineKeyboardButton(text="👥 Просмотреть участников", callback_data=f"event_users:{event_id}")],
        [InlineKeyboardButton(text="📅 Добавить в календарь (.ics)", callback_data=f"event_ics:{event_id}")],
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
        registered_count = count_event_registrations(event_id)
        participants_line = f"👥 Участников {registered_count}/{max_p}"
        if registered_count >= max_p:
            participants_line += " — солдаут!"

        text = (
            f"🎬 <b>{name}</b>\n"
            f"📝 {desc}\n\n"
            f"💰 Цена: {price}\n"
            f"🏠 Адрес: {address}\n"
            f"{participants_line}\n"
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
    await call.message.edit_reply_markup(
        reply_markup=event_edit_kb(event_id)
    )


@router.callback_query(lambda c: c.data.startswith("event_back:"))
async def event_back(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    await call.message.edit_reply_markup(
        reply_markup=event_main_kb(event_id)
    )



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


@router.callback_query(lambda c: c.data.startswith("event_ics:"))
async def event_send_ics(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    event_row = get_event(event_id)
    if not event_row:
        await call.answer("Ивент не найден", show_alert=True)
        return

    filename, content = build_event_ics(event_row)
    ics_file = BufferedInputFile(content, filename=filename)
    await call.message.answer_document(ics_file, caption="📅 Файл календаря")
    await call.answer()


@router.callback_query(lambda c: c.data.startswith("event_edit_"))
async def start_edit_field(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    action = parts[0]          # event_edit_price
    event_id = int(parts[1])   # ID ивента

    field_key = action.replace("event_edit_", "")

    if field_key not in EDIT_FIELDS:
        await call.answer("Неизвестное поле", show_alert=True)
        return

    label, db_field = EDIT_FIELDS[field_key]

    await state.set_state(EditEventState.value)
    await state.update_data(
        event_id=event_id,
        field=db_field,
        field_key=field_key
    )

    await call.message.answer(f"✏️ Введите новое значение для поля «{label}»:")


@router.message(EditEventState.value)
async def apply_edit(message: Message, state: FSMContext):
    data = await state.get_data()

    event_id = data["event_id"]
    field = data["field"]
    field_key = data["field_key"]
    value = message.text.strip()

    # --- Валидация (минимальная, но корректная) ---
    try:
        if field_key == "price":
            value = float(value)
            if value < 0:
                raise ValueError

        elif field_key == "max":
            value = int(value)
            if value <= 0:
                raise ValueError

        elif field_key == "date":
            day, month = map(int, value.split("."))
            now = datetime.now()
            year = now.year
            dt = datetime(year, month, day)
            if dt.date() < now.date():
                dt = datetime(year + 1, month, day)
            value = dt.strftime("%Y-%m-%d")

        elif field_key == "time":
            datetime.strptime(value, "%H:%M")

    except Exception:
        await message.answer("⚠️ Неверный формат. Попробуй ещё раз.")
        return

    update_event_field(event_id, field, value)

    await message.answer("✅ Значение обновлено.")
    await state.clear()
