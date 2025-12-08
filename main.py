import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

from config import TOKEN
from database import MainDb
import handlers

# Логи в файл и консоль — надёжная версия
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Убираем старые хендлеры, если они есть
if logger.handlers:
    logger.handlers.clear()

# Хендлер для файла
file_handler = logging.FileHandler("bot.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Хендлер для консоли
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(file_formatter)
logger.addHandler(console_handler)

logging.info("Логи успешно настроены — теперь всё будет писаться в bot.log")

bot = Bot(token=TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Регистрация всех хендлеров
handlers.register_all(dp)

async def on_startup(_):
    db = MainDb()
    db.create_tables()
    logging.info("Бот запущен и готов к работе!")

if __name__ == '__main__':
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )