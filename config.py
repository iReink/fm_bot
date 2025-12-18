from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Загружаем токен из файла token
TOKEN_PATH = BASE_DIR / "token"

try:
    BOT_TOKEN = TOKEN_PATH.read_text(encoding="utf-8").strip()
except FileNotFoundError:
    raise RuntimeError("Файл token не найден. Создай файл token и положи туда токен бота.")

if not BOT_TOKEN:
    raise RuntimeError("Файл token пустой.")

# Список администраторов
ADMINS = [
    884940984,
    165034212,
]
