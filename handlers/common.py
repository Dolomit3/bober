import asyncio
import logging
import re
from datetime import datetime
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import MessageNotModified
from config import ADMINS_ID
import database
from utils import send_captcha, lift_restrictions, check_bot_permissions
from handlers.menu import show_main_menu  # импорт меню

db = database.MainDb()

# ===================== /start =====================
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    is_admin = message.from_user.id in ADMINS_ID
    # Можно оставить приветственный текст, если нужно
    if is_admin:
        await message.answer("Добро пожаловать, админ! Выберите действие из меню ниже:")
    else:
        await message.answer("Добро пожаловать! Используйте кнопки меню ниже:")
    # Показываем меню
    await show_main_menu(message)

# ===================== Вступление/выход из чата =====================
async def handle_new_member(update: types.ChatMemberUpdated, state: FSMContext):
    new_member = update.new_chat_member
    chat_id = update.chat.id
    user_id = new_member.user.id

    if user_id == (await update.bot.get_me()).id:
        return

    if not await check_bot_permissions(update.bot, chat_id):
        return

    if new_member.status in ['left', 'kicked', 'banned']:
        db.delete_captcha_status(user_id, chat_id)
        logging.info(f"Captcha status deleted for user {user_id} in chat {chat_id} (user left)")

# ===================== Ответ на капчу =====================
async def check_captcha(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    try:
        _, selected_answer, cb_chat_id, cb_user_id = call.data.split("_")
        selected_answer = int(selected_answer)
        cb_chat_id = int(cb_chat_id)
        cb_user_id = int(cb_user_id)
    except ValueError:
        await call.answer("Ошибка капчи.", show_alert=True)
        return

    if user_id != cb_user_id or chat_id != cb_chat_id:
        await call.answer("Это не ваша капча!")
        return

    attempts = db.increment_captcha_attempts(user_id, chat_id)

    # Определяем правильный ответ
    question_line = call.message.text.split("\n")[1] if "\n" in call.message.text else ""
    match = re.search(r'(\d+)\s*\+\s*(\d+)', question_line)
    if not match:
        await call.answer("Ошибка в вопросе капчи.")
        return
    correct_answer = int(match.group(1)) + int(match.group(2))

    if selected_answer == correct_answer:
        db.update_captcha_status(user_id, chat_id)
        if await lift_restrictions(call.bot, chat_id, user_id):
            try:
                await call.message.delete()
            except Exception as e:
                logging.warning(f"Не удалось удалить капчу {call.message.message_id}: {e}")
            await call.answer("Капча пройдена! Вы можете писать в чат.", show_alert=True)
        return

    remaining = 3 - attempts
    try:
        await call.message.delete()
    except Exception as e:
        logging.warning(f"Не удалось удалить капчу {call.message.message_id}: {e}")

    if remaining > 0:
        await call.answer(f"Неверно! Осталось попыток: {remaining}")
        await asyncio.sleep(0.5)
        await send_captcha(call.bot, call, user_id, chat_id, state)
    else:
        await call.answer("Превышено количество попыток. Вы забанены на 24 часа.", show_alert=True)

# ===================== Обработка обычных сообщений в чате =====================
async def message_in_chat(message: types.Message, state: FSMContext):
    if message.chat.type not in ["group", "supergroup"]:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        if member.status in ['left', 'kicked', 'banned']:
            return
        if member.status in ['creator', 'administrator']:
            db.update_last_message_time(user_id, chat_id)
            return
    except Exception as e:
        logging.error(f"Ошибка получения статуса пользователя {user_id} в чате {chat_id}: {e}")
        return

    # Кулдаун
    cooldown = db.get_message_cooldown(chat_id)
    if cooldown > 0:
        last_time = db.get_last_message_time(user_id, chat_id)
        if last_time and (datetime.now() - last_time).total_seconds() < cooldown:
            try:
                await message.delete()
                remaining = int(cooldown - (datetime.now() - last_time).total_seconds())
                noti = await message.answer(f"Подождите ещё {remaining} сек.")
                await asyncio.sleep(10)
                await noti.delete()
            except Exception as e:
                logging.warning(f"Ошибка при удалении/уведомлении сообщения {message.message_id}: {e}")
            return

    # Капча и стоп-слова
    if db.have_stop_words(chat_id):
        if not db.check_captcha_status(user_id, chat_id):
            try:
                await message.delete()
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение {message.message_id} для капчи: {e}")

            old_msg_id = db.get_captcha_message_id(user_id, chat_id)
            if old_msg_id:
                try:
                    await message.bot.delete_message(chat_id, old_msg_id)
                except Exception as e:
                    logging.warning(f"Не удалось удалить старую капчу {old_msg_id}: {e}")

            db.delete_captcha_status(user_id, chat_id)

            try:
                member = await message.bot.get_chat_member(chat_id, user_id)
                if member.status in ['left', 'kicked', 'banned']:
                    return
            except:
                return

            await send_captcha(message.bot, message, user_id, chat_id, state)
            return

        # Проверка стоп-слов
        text = (message.text or message.caption or "").lower()
        text_words = re.findall(r'\w+', text, flags=re.UNICODE)
        stop_words = {w.lower() for w in db.get_all_stop_words()}
        if any(word in stop_words for word in text_words):
            try:
                await message.delete()
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение с стоп-словом {message.message_id}: {e}")
            return

    db.update_last_message_time(user_id, chat_id)

# ===================== Регистрация =====================
def register_common_handlers(dp):
    dp.register_message_handler(cmd_start, commands=['start'])
    dp.register_chat_member_handler(handle_new_member)
    dp.register_callback_query_handler(check_captcha, text_contains="captcha_")
    dp.register_message_handler(message_in_chat, content_types=types.ContentType.ANY,
                                chat_type=[types.ChatType.GROUP, types.ChatType.SUPERGROUP])