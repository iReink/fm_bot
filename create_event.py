import sqlite3
from aiogram import Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data.db"
PICS_DIR = Path(__file__).resolve().parent / "pics"
router = Router()

DASH_SYMBOLS = {"-", "—", "–", "−", "‑"}

# --- FSM состояния ---
class EventStates(StatesGroup):
    name = State()
    description = State()
    price = State()
    address = State()
    max_participants = State()
    date = State()
    time = State()
    poster = State()

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
def save_event(data: dict) -> int:
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
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id


def is_skip_poster(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return all(symbol in DASH_SYMBOLS for symbol in stripped)


async def save_event_poster(message: Message, event_id: int) -> None:
    PICS_DIR.mkdir(parents=True, exist_ok=True)
    poster_path = PICS_DIR / f"{event_id}.png"
    photo = message.photo[-1]
    await message.bot.download(photo, destination=poster_path)

# --- Старт создания ивента ---
async def start_new_event(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🎬 Создаём новый ивент!\nВведите название:", reply_markup=cancel_button)
    await state.set_state(EventStates.name)

# --- Хендлеры FSM ---
@router.message(EventStates.name)
async def event_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📝 Введите описание ивента:", reply_markup=cancel_button)
    await state.set_state(EventStates.description)

@router.message(EventStates.description)
async def event_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    last = get_last_event()
    if last:
        buttons = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"💰 {last[2]}", callback_data="price_fill")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
            ]
        )

    else:
        buttons = cancel_button
    await message.answer("💰 Введите цену билета:", reply_markup=buttons)
    await state.set_state(EventStates.price)

@router.message(EventStates.price)
async def event_price(message: Message, state: FSMContext):
    last = get_last_event()
    if last and message.text == f"💰 {last[2]}":
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

    last = get_last_event()
    if last and last[0]:
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🏠 {last[0]}", callback_data="address_fill")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
        ])
    else:
        buttons = cancel_button
    await message.answer("🏠 Введите адрес проведения:", reply_markup=buttons)
    await state.set_state(EventStates.address)

@router.message(EventStates.address)
async def event_address(message: Message, state: FSMContext):
    last = get_last_event()
    if last and message.text == f"🏠 {last[0]}":
        address = last[0]
    else:
        address = message.text
    await state.update_data(address=address)

    if last and last[1]:
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"👥 {last[1]}", callback_data="max_fill")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
        ])
    else:
        buttons = cancel_button
    await message.answer("👥 Введите максимальное количество участников:", reply_markup=buttons)
    await state.set_state(EventStates.max_participants)

@router.message(EventStates.max_participants)
async def event_max(message: Message, state: FSMContext):
    last = get_last_event()
    if last and message.text == f"👥 {last[1]}":
        max_participants = int(last[1])
    else:
        try:
            max_participants = int(message.text)
            if max_participants <= 0:
                raise ValueError
        except ValueError:
            await message.answer("⚠️ Введите целое положительное число:", reply_markup=cancel_button)
            return
    await state.update_data(max_participants=max_participants)
    await message.answer("📅 Введите дату в формате DD.MM (например, 25.12):", reply_markup=cancel_button)
    await state.set_state(EventStates.date)

@router.message(EventStates.date)
async def event_date(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        day, month = map(int, text.split("."))
        now = datetime.now()
        year = now.year
        dt = datetime(year, month, day)
        if dt.date() < now.date():
            dt = datetime(year + 1, month, day)
        date_str = dt.strftime("%Y-%m-%d")

    except Exception:
        await message.answer("⚠️ Неверный формат даты. Используйте DD.MM:", reply_markup=cancel_button)
        return
    await state.update_data(date=date_str)

    last = get_last_event()
    if last and last[3]:
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⏰ {last[3]}", callback_data="time_fill")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
        ])
    else:
        buttons = cancel_button
    await message.answer("⏰ Введите время в формате HH:MM (например, 18:30):", reply_markup=buttons)
    await state.set_state(EventStates.time)

@router.message(EventStates.time)
async def event_time(message: Message, state: FSMContext):
    last = get_last_event()
    if last and message.text == f"⏰ {last[3]}":
        time_str = last[3]
    else:
        try:
            datetime.strptime(message.text.strip(), "%H:%M")
            time_str = message.text.strip()
        except ValueError:
            await message.answer("⚠️ Неверный формат времени. Используйте HH:MM:", reply_markup=cancel_button)
            return
    await state.update_data(time=time_str)
    data = await state.get_data()
    event_id = save_event(data)
    await state.update_data(event_id=event_id)
    await message.answer(
        "🖼️ Отправьте афишу для ивента или пропустите шаг.\n"
        "Если афиша не нужна — отправьте «-» (подойдут разные тире).",
        reply_markup=cancel_button,
    )
    await state.set_state(EventStates.poster)


@router.message(EventStates.poster)
async def event_poster(message: Message, state: FSMContext):
    data = await state.get_data()
    event_id = data["event_id"]
    poster_path = PICS_DIR / f"{event_id}.png"

    if message.photo:
        await save_event_poster(message, event_id)
    elif message.text and is_skip_poster(message.text):
        if poster_path.exists():
            poster_path.unlink()
    else:
        await message.answer(
            "⚠️ Отправьте картинку или «-», если хотите пропустить.",
            reply_markup=cancel_button,
        )
        return

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

@router.callback_query(lambda call: call.data == "cancel_event")
async def cancel_event(call, state: FSMContext):
    await state.clear()
    await call.message.answer("❌ Создание ивента отменено.")

# --- Хендлер автозаполнения цены ---
@router.callback_query(lambda c: c.data == "price_fill")
async def fill_price(call, state: FSMContext):
    last = get_last_event()
    if last:
        await state.update_data(price=last[2])
        # Переход к адресу
        if last and last[0]:
            buttons = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🏠 {last[0]}", callback_data="address_fill")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
            ])
        else:
            buttons = cancel_button
        await call.message.edit_text("🏠 Введите адрес проведения:", reply_markup=buttons)
        await state.set_state(EventStates.address)

# --- Хендлер автозаполнения адреса ---
@router.callback_query(lambda c: c.data == "address_fill")
async def fill_address(call, state: FSMContext):
    last = get_last_event()
    if last:
        await state.update_data(address=last[0])
        # Переход к макс. участникам
        if last and last[1]:
            buttons = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"👥 {last[1]}", callback_data="max_fill")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
            ])
        else:
            buttons = cancel_button
        await call.message.edit_text("👥 Введите максимальное количество участников:", reply_markup=buttons)
        await state.set_state(EventStates.max_participants)

# --- Хендлер автозаполнения макс. участников ---
@router.callback_query(lambda c: c.data == "max_fill")
async def fill_max(call, state: FSMContext):
    last = get_last_event()
    if last:
        await state.update_data(max_participants=int(last[1]))
        # Переход к дате
        await call.message.edit_text("📅 Введите дату в формате DD.MM (например, 25.12):", reply_markup=cancel_button)
        await state.set_state(EventStates.date)

# --- Хендлер автозаполнения времени ---
@router.callback_query(lambda c: c.data == "time_fill")
async def fill_time(call, state: FSMContext):
    last = get_last_event()
    if last:
        await state.update_data(time=last[3])
        data = await state.get_data()
        event_id = save_event(data)
        await state.update_data(event_id=event_id)
        await call.message.edit_text(
            "🖼️ Отправьте афишу для ивента или пропустите шаг.\n"
            "Если афиша не нужна — отправьте «-» (подойдут разные тире).",
            reply_markup=cancel_button,
        )
        await state.set_state(EventStates.poster)
