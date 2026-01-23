import asyncio
import sqlite3
from datetime import datetime, time
from pathlib import Path

from aiogram import Router, Bot
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BufferedInputFile,
)

from ics_utils import build_event_ics
DB_PATH = Path(__file__).resolve().parent / "data.db"
router = Router()

REMINDER_WINDOW_MINUTES = 2
REMINDER_TIME = time(10, 0)
REMINDER_CHECK_INTERVAL_SECONDS = 60
_sent_reminders: dict[str, set[tuple[int, int]]] = {}


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


def get_user_notification_setting(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT notification_on FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return True
    return bool(row[0])


def set_user_notification_setting(user_id: int, enabled: bool):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET notification_on = ? WHERE user_id = ?",
        (1 if enabled else 0, user_id),
    )
    conn.commit()
    conn.close()


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


def add_log_entry(user_id: int, user_name: str, user_nickname: str, description: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now()
    cursor.execute(
        """
        INSERT INTO logs (user_id, user_name, user_nickname, description, log_date, log_time)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            user_name,
            user_nickname,
            description,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
        ),
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
    add_calendar_button = InlineKeyboardButton(
        text="📅 Добавить в календарь (.ics)",
        callback_data=f"user_ics:{event_id}",
    )
    if is_user_registered(event_id, user_id):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить регистрацию", callback_data=f"user_cancel:{event_id}")],
                [add_calendar_button],
            ]
        )
    if is_full:
        return InlineKeyboardMarkup(inline_keyboard=[[add_calendar_button]])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Записаться", callback_data=f"user_register:{event_id}")],
            [add_calendar_button],
        ]
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


def build_participant_menu(notification_on: bool) -> ReplyKeyboardMarkup:
    notification_button = (
        "Выключить напоминания" if notification_on else "Включить напоминания"
    )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Ивенты, в которых я участвую")],
            [KeyboardButton(text="Все ивенты")],
            [KeyboardButton(text=notification_button)],
        ],
        resize_keyboard=True,
    )


async def send_nearest_event(message: Message):
    events = get_future_events(limit=1)
    if not events:
        menu = build_participant_menu(get_user_notification_setting(message.from_user.id))
        await message.answer("📭 Будущих ивентов пока нет.", reply_markup=menu)
        return

    event_row = events[0]
    text, keyboard = build_event_card(event_row, message.from_user.id)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    menu = build_participant_menu(get_user_notification_setting(message.from_user.id))
    await message.answer("Выберите, что хотите посмотреть:", reply_markup=menu)


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


@router.message(lambda msg: msg.text in ["Включить напоминания", "Выключить напоминания"])
async def toggle_notifications(message: Message):
    enable_notifications = message.text == "Включить напоминания"
    set_user_notification_setting(message.from_user.id, enable_notifications)
    status_text = "Напоминания включены ✅" if enable_notifications else "Напоминания выключены ✅"
    menu = build_participant_menu(enable_notifications)
    await message.answer(status_text, reply_markup=menu)


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
        add_log_entry(
            call.from_user.id,
            user_name,
            user_nickname,
            f"Регистрация на ивент «{event_row[1]}»",
        )

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

    add_log_entry(
        call.from_user.id,
        call.from_user.full_name,
        call.from_user.username or "",
        f"Отмена регистрации на ивент «{event_row[1]}»",
    )

    text, keyboard = build_event_card(event_row, call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer("Регистрация отменена")


def build_reminder_text(event_row) -> str:
    return f"Напоминаем о событии сегодня!\n\n{format_event_text(event_row, is_full=False)}"


def build_reminder_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отписаться", callback_data=f"reminder_unsubscribe:{event_id}")],
            [InlineKeyboardButton(text="Выключить уведомления", callback_data="reminder_disable_notifications")],
        ]
    )


def get_today_event_participants():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT e.event_id, e.name, e.description, e.price, e.address,
               e.max_participants, e.event_date, e.event_time,
               r.user_id, u.username, u.nickname
        FROM events e
        JOIN registrations r ON r.event_id = e.event_id
        JOIN users u ON u.user_id = r.user_id
        WHERE e.is_deleted = 0
          AND date(e.event_date) = date('now')
          AND u.notification_on = 1
        ORDER BY e.event_date, e.event_time
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def is_time_in_window(now: datetime) -> bool:
    window_start = time(
        REMINDER_TIME.hour,
        max(0, REMINDER_TIME.minute - REMINDER_WINDOW_MINUTES),
    )
    window_end = time(
        REMINDER_TIME.hour,
        min(59, REMINDER_TIME.minute + REMINDER_WINDOW_MINUTES),
    )
    return window_start <= now.time() <= window_end


async def send_event_reminders(bot: Bot):
    now = datetime.now()
    if not is_time_in_window(now):
        return

    today_key = now.strftime("%Y-%m-%d")
    sent_today = _sent_reminders.setdefault(today_key, set())
    for row in get_today_event_participants():
        event_id = row[0]
        user_id = row[8]
        reminder_key = (event_id, user_id)
        if reminder_key in sent_today:
            continue

        text = build_reminder_text(row[:8])
        keyboard = build_reminder_keyboard(event_id)
        await bot.send_message(user_id, text, reply_markup=keyboard, parse_mode="HTML")
        sent_today.add(reminder_key)


async def reminder_loop(bot: Bot):
    while True:
        now = datetime.now()
        today_key = now.strftime("%Y-%m-%d")
        if list(_sent_reminders.keys()) != [today_key]:
            _sent_reminders.clear()
        try:
            await send_event_reminders(bot)
        except Exception:
            pass
        await asyncio.sleep(REMINDER_CHECK_INTERVAL_SECONDS)


@router.callback_query(lambda c: c.data.startswith("reminder_unsubscribe:"))
async def reminder_unsubscribe(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    cancel_user_registration(event_id, call.from_user.id)
    event_row = get_event_by_id(event_id)
    if not event_row:
        await call.answer("Ивент не найден", show_alert=True)
        return

    add_log_entry(
        call.from_user.id,
        call.from_user.full_name,
        call.from_user.username or "",
        f"Отписка от напоминания на ивент «{event_row[1]}»",
    )

    text, keyboard = build_event_card(event_row, call.from_user.id)
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer("Вы отписались")


@router.callback_query(lambda c: c.data == "reminder_disable_notifications")
async def reminder_disable_notifications(call: CallbackQuery):
    set_user_notification_setting(call.from_user.id, False)
    await call.answer("Уведомления выключены")


@router.callback_query(lambda c: c.data.startswith("user_ics:"))
async def user_send_ics(call: CallbackQuery):
    event_id = int(call.data.split(":")[1])
    event_row = get_event_by_id(event_id)
    if not event_row:
        await call.answer("Ивент не найден", show_alert=True)
        return

    filename, content = build_event_ics(event_row)
    ics_file = BufferedInputFile(content, filename=filename)
    await call.message.answer_document(ics_file, caption="📅 Файл календаря")
    await call.answer()
