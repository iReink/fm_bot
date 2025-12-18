import sqlite3
from aiogram import Router, F
from aiogram.filters import Text
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data.db"
router = Router()

# --- FSM состояния ---
class EventStates(StatesGroup):
    name = State()
    description = State()
    price = State()
    address = State()
    max_participants = State()
    date = State()
    time = State()

# --- Кнопка отмены ---
cancel_button = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
])

# --- Получение последнего ивента для автозаполнения ---
def get_last_event():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT address, max_participants, price, event_time FROM events ORDER BY event_id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row  # None, если нет предыдущих ивентов

# --- Сохраняем новый ивент ---
def save_event(data: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO events (name, description, price, address, max_participants, event_date, event_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data['name'],
        data['description'],
        data['price'],
        data['address'],
        data['max_participants'],
        data['date'],
        data['time']
    ))
    conn.commit()
    conn.close()

# --- Старт создания ивента ---
@router.message(Text(text="Новый ивент"))
async def start_new_event(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🎬 Создаём новый ивент!\nВведите название:", reply_markup=cancel_button)
    await state.set_state(EventStates.name)

# --- Ввод названия ---
@router.message(EventStates.name)
async def event_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📝 Введите описание ивента:", reply_markup=cancel_button)
    await state.set_state(EventStates.description)

# --- Ввод описания ---
@router.message(EventStates.description)
async def event_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    last = get_last_event()
    if last:
        price_buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 {last[2]}", callback_data=f"price_fill")]
        ])
    else:
        price_buttons = None
    await message.answer("💰 Введите цену билета:", reply_markup=price_buttons or cancel_button)
    await state.set_state(EventStates.price)

# --- Ввод цены ---
@router.message(EventStates.price)
async def event_price(message: Message, state: FSMContext):
    data = await state.get_data()
    last = get_last_event()
    if message.text == "💰 " + str(last[2]) if last else False:
        price = last[2]
    else:
        try:
            price = float(message.text)
            if price < 0:
                raise ValueError
        except ValueError:
            await message.answer("⚠️ Введите корректную цену (число ≥ 0). Попробуйте снова:", reply_markup=cancel_button)
            return
    await state.update_data(price=price)

    # Адрес с автозаполнением
    if last and last[0]:
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🏠 {last[0]}", callback_data="address_fill")]
        ])
    else:
        buttons = None

    await message.answer("🏠 Введите адрес проведения:", reply_markup=buttons or cancel_button)
    await state.set_state(EventStates.address)

# --- Ввод адреса ---
@router.message(EventStates.address)
async def event_address(message: Message, state: FSMContext):
    last = get_last_event()
    if message.text.startswith("🏠 ") and last:
        address = last[0]
    else:
        address = message.text
    await state.update_data(address=address)

    # Максимальное количество участников с автозаполнением
    if last and last[1]:
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"👥 {last[1]}", callback_data="max_fill")]
        ])
    else:
        buttons = None
    await message.answer("👥 Введите максимальное количество участников:", reply_markup=buttons or cancel_button)
    await state.set_state(EventStates.max_participants)

# --- Ввод максимального количества участников ---
@router.message(EventStates.max_participants)
async def event_max(message: Message, state: FSMContext):
    last = get_last_event()
    if message.text.startswith("👥 ") and last:
        max_participants = int(last[1])
    else:
        try:
            max_participants = int(message.text)
            if max_participants <= 0:
                raise ValueError
        except ValueError:
            await message.answer("⚠️ Введите целое положительное число для участников:", reply_markup=cancel_button)
            return
    await state.update_data(max_participants=max_participants)
    last_time = last[3] if last else None

    # Дата
    await message.answer("📅 Введите дату в формате MM.DD (например, 12.25):", reply_markup=cancel_button)
    await state.set_state(EventStates.date)

# --- Ввод даты ---
@router.message(EventStates.date)
async def event_date(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        month, day = map(int, text.split("."))
        now = datetime.now()
        year = now.year
        dt = datetime(year, month, day)
        if dt.date() < now.date():
            dt = datetime(year + 1, month, day)
        date_str = dt.strftime("%Y-%m-%d")
    except Exception:
        await message.answer("⚠️ Неверный формат даты. Используйте MM.DD (например, 12.25):", reply_markup=cancel_button)
        return
    await state.update_data(date=date_str)

    last = get_last_event()
    if last and last[3]:
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⏰ {last[3]}", callback_data="time_fill")]
        ])
    else:
        buttons = None

    await message.answer("⏰ Введите время в формате HH:MM (например, 18:30):", reply_markup=buttons or cancel_button)
    await state.set_state(EventStates.time)

# --- Ввод времени ---
@router.message(EventStates.time)
async def event_time(message: Message, state: FSMContext):
    text = message.text.strip()
    last = get_last_event()
    if text.startswith("⏰ ") and last:
        time_str = last[3]
    else:
        try:
            datetime.strptime(text, "%H:%M")
            time_str = text
        except ValueError:
            await message.answer("⚠️ Неверный формат времени. Используйте HH:MM (например, 18:30):", reply_markup=cancel_button)
            return
    await state.update_data(time=time_str)

    # Сохраняем данные
    data = await state.get_data()
    save_event(data)

    # Подтверждение
    await message.answer(
        f"✅ Ивент создан!\n\n"
        f"🎬 Название: {data['name']}\n"
        f"📝 Описание: {data['description']}\n"
        f"💰 Цена: {data['price']}\n"
        f"🏠 Адрес: {data['address']}\n"
        f"👥 Макс. участников: {data['max_participants']}\n"
        f"📅 Дата: {data['date']}\n"
        f"⏰ Время: {data['time']}"
    )
    await state.clear()

# --- Отмена ---
@router.callback_query(Text(text="cancel_event"))
async def cancel_event(call, state: FSMContext):
    await state.clear()
    await call.message.answer("❌ Создание ивента отменено.")
