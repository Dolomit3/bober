import logging
import re

from aiogram import types
from aiogram.dispatcher import FSMContext

from config import ADMINS_ID
import database
from utils import send_captcha, lift_restrictions, check_bot_permissions

db = database.MainDb()


# ===================== Добавление чата =====================
async def add_chat(message: types.Message):
    logging.info(f"Получена команда /add_chat от {message.from_user.id} в чате {message.chat.id} ({message.chat.type})")

    if message.chat.type == "private":
        await message.answer("Команда /add_chat только в групповом чате.")
        logging.info("/add_chat в ЛС — отклонено")
        return

    permissions_ok = await check_bot_permissions(message.bot, message.chat.id)
    logging.info(f"Проверка прав бота в чате {message.chat.id}: {'ОК' if permissions_ok else 'НЕТ'}")

    if not permissions_ok:
        await message.answer("Боту не хватает прав для работы.\nНужны: удаление сообщений, блокировка пользователей, закрепление сообщений.")
        return

    try:
        db.add_chat(message.chat.id)
        logging.info(f"Чат {message.chat.id} успешно добавлен в базу")
        await message.answer(
            "Чат успешно добавлен. Все функции (закреп, автопостинг, капча, стоп-слова) включены.\n"
            "Отключить можно командами /turn_off_pinning и т.д."
        )
    except Exception as e:
        logging.error(f"Ошибка при добавлении чата {message.chat.id} в базу: {e}")
        await message.answer("Произошла ошибка при добавлении чата. Смотрите bot.log")


# ===================== Управление капчей =====================
async def reset_captcha(message: types.Message):
    if message.from_user.id not in ADMINS_ID:
        return
    try:
        user_id = int(message.text.split()[1])
        db.delete_captcha_status(user_id, message.chat.id)
        await message.answer(f"Капча сброшена для {user_id}")
    except:
        await message.answer("Укажите ID: /reset_captcha <user_id>")


async def reset_captcha_attempts(message: types.Message):
    if message.from_user.id not in ADMINS_ID:
        return
    try:
        user_id = int(message.text.split()[1])
        db.reset_captcha_attempts(user_id, message.chat.id)
        await message.answer(f"Попытки сброшены для {user_id}")
    except:
        await message.answer("Укажите ID: /reset_captcha_attempts <user_id>")


async def force_captcha_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS_ID:
        return
    try:
        user_id = int(message.text.split()[1])
        await send_captcha(message.bot, message, user_id, message.chat.id, state)
        await message.answer(f"Капча отправлена {user_id}")
    except:
        await message.answer("Укажите ID: /force_captcha <user_id>")


async def check_user(message: types.Message):
    if message.from_user.id not in ADMINS_ID:
        return
    try:
        user_id = int(message.text.split()[1])
        member = await message.bot.get_chat_member(message.chat.id, user_id)
        captcha_status = db.check_captcha_status(user_id, message.chat.id)
        attempts = db.get_captcha_attempts(user_id, message.chat.id)
        cooldown = db.get_message_cooldown(message.chat.id)
        text = f"Пользователь {user_id}\nСтатус: {member.status}\nКапча: {'пройдена' if captcha_status else 'не пройдена'}\nПопыток: {attempts}\nКулдаун чата: {cooldown} сек"
        await message.answer(text)
    except:
        await message.answer("Укажите ID: /check_user <user_id>")


async def unrestrict_user(message: types.Message):
    if message.from_user.id not in ADMINS_ID:
        return
    try:
        user_id = int(message.text.split()[1])
        if await lift_restrictions(message.bot, message.chat.id, user_id):
            await message.answer(f"Ограничения сняты с {user_id}")
        else:
            await message.answer("Не удалось снять ограничения")
    except:
        await message.answer("Укажите ID: /unrestrict_user <user_id>")


# ===================== Информация о чатах =====================
async def debug_chats(message: types.Message):
    if message.from_user.id not in ADMINS_ID:
        return
    chats = db.get_all_chats()
    text = "Чаты в базе:\n"
    for c in chats:
        text += f"ID: {c[0]} | стоп-слова: {c[3]} | автопост: {c[1]} | закреп: {c[2]}\n"
    await message.answer(text or "Нет чатов")


# ===================== Включение/выключение функций =====================
async def turn_on_stopwords(message: types.Message):
    db.update_chat_settings(message.chat.id, has_stopwords=1)
    await message.answer("Стоп-слова и капча включены")


async def turn_off_stopwords(message: types.Message):
    db.update_chat_settings(message.chat.id, has_stopwords=0)
    await message.answer("Стоп-слова и капча выключены")


async def turn_on_pinning(message: types.Message):
    db.update_chat_settings(message.chat.id, has_autopining=1)
    await message.answer("Закрепление включено")


async def turn_off_pinning(message: types.Message):
    db.update_chat_settings(message.chat.id, has_autopining=0)
    await message.answer("Закрепление выключено")


async def turn_on_autoposting(message: types.Message):
    db.update_chat_settings(message.chat.id, has_autoposting=1)
    await message.answer("Автопостинг включён")


async def turn_off_autoposting(message: types.Message):
    db.update_chat_settings(message.chat.id, has_autoposting=0)
    await message.answer("Автопостинг выключен")


# ===================== Настройки времени =====================
async def set_message_cooldown(message: types.Message):
    if message.from_user.id not in ADMINS_ID:
        return
    try:
        args = message.text.split()
        seconds = int(args[1])
        if seconds < 0 or seconds > 86400:
            await message.answer("0–86400 секунд")
            return
        if len(args) > 2 and args[2] == "--all":
            for chat in db.get_all_chats():
                db.set_message_cooldown(chat[0], seconds)
            await message.answer(f"Кулдаун {seconds} сек для всех чатов")
        else:
            db.set_message_cooldown(message.chat.id, seconds)
            await message.answer(f"Кулдаун {seconds} сек для этого чата")
    except:
        await message.answer("Использование: /set_message_cooldown <секунды> [--all]")


async def get_message_cooldown(message: types.Message):
    cooldown = db.get_message_cooldown(message.chat.id)
    await message.answer(f"Текущий кулдаун: {cooldown} сек")


async def set_captcha_timeout(message: types.Message):
    if message.from_user.id not in ADMINS_ID:
        return
    try:
        timeout = int(message.text.split()[1])
        if not 60 <= timeout <= 3600:
            await message.answer("60–3600 секунд")
            return
        db.set_captcha_timeout(message.chat.id, timeout)
        await message.answer(f"Таймаут капчи: {timeout} сек")
    except:
        await message.answer("Укажите секунды: /set_captcha_timeout <seconds>")


# ===================== Удаление чата =====================
async def delete_chat(message: types.Message):
    if message.from_user.id in ADMINS_ID:
        if db.delete_chat(message.chat.id):
            await message.answer("Чат удалён из базы")
        else:
            await message.answer("Чата нет в базе")


# ===================== Обработка стоп-слов через файл =====================
async def handle_document(message: types.Message):
    if message.from_user.id not in ADMINS_ID:
        return
    if not message.document or message.document.mime_type != "text/plain":
        await message.answer("Пришлите .txt файл со стоп-словами через запятую")
        return
    try:
        file_path = await message.document.download()
        with open(file_path.name, "r", encoding="utf-8") as f:
            content = f.read()

        words = [w.strip().lower() for w in content.split(",") if w.strip()]
        db.update_stop_words(words)
        await message.answer(f"Обновлено стоп-слов: {len(words)}")
    except Exception as e:
        logging.error(f"Ошибка загрузки стоп-слов: {e}")
        await message.answer("Ошибка обработки файла")


# ===================== Регистрация хэндлеров =====================
def register_admin_handlers(dp):
    dp.register_message_handler(add_chat, commands=["add_chat"], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
    dp.register_message_handler(reset_captcha, commands=["reset_captcha"])
    dp.register_message_handler(reset_captcha_attempts, commands=["reset_captcha_attempts"])
    dp.register_message_handler(force_captcha_cmd, commands=["force_captcha"])
    dp.register_message_handler(check_user, commands=["check_user"])
    dp.register_message_handler(unrestrict_user, commands=["unrestrict_user"])
    dp.register_message_handler(debug_chats, commands=["debug_chats"])
    dp.register_message_handler(turn_on_stopwords, commands=["turn_on_stopwords"], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
    dp.register_message_handler(turn_off_stopwords, commands=["turn_off_stopwords"], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
    dp.register_message_handler(turn_on_pinning, commands=["turn_on_pinning"], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
    dp.register_message_handler(turn_off_pinning, commands=["turn_off_pinning"], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
    dp.register_message_handler(turn_on_autoposting, commands=["turn_on_autoposting"], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
    dp.register_message_handler(turn_off_autoposting, commands=["turn_off_autoposting"], chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])
    dp.register_message_handler(set_message_cooldown, commands=["set_message_cooldown"])
    dp.register_message_handler(get_message_cooldown, commands=["get_message_cooldown"])
    dp.register_message_handler(set_captcha_timeout, commands=["set_captcha_timeout"])
    dp.register_message_handler(delete_chat, commands=["delete_chat"])
    dp.register_message_handler(handle_document, content_types=types.ContentType.DOCUMENT)