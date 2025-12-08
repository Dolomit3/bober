import asyncio
import logging
import random
import re
from datetime import datetime, timedelta

from aiogram import types

import database
from keyboards import get_captcha_keyboard

db = database.MainDb()


# Генерация простой капчи
def generate_captcha():
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    answer = a + b
    question = f"Сколько будет {a} + {b}?"
    logging.info(f"[CAPTCHA] Сгенерирован вопрос: {question}, ответ: {answer}")
    return question, answer


# Проверка прав бота
async def check_bot_permissions(bot, chat_id: int) -> bool:
    try:
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        return (
            bot_member.can_delete_messages
            and bot_member.can_restrict_members
            and bot_member.can_pin_messages
            and bot_member.can_manage_chat
        )
    except Exception as e:
        logging.error(f"[ERROR] Не удалось проверить права бота в чате {chat_id}: {e}")
        return False


# Снятие ограничений
async def lift_restrictions(bot, chat_id: int, user_id: int):
    for attempt in range(3):
        try:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=types.ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_change_info=True,
                    can_invite_users=True,
                    can_pin_messages=True
                )
            )
            await asyncio.sleep(2)
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status == "member":
                logging.info(f"[CAPTCHA] Ограничения сняты: user={user_id}")
                return True
        except Exception as e:
            logging.error(f"[ERROR] Ошибка снятия ограничений (попытка {attempt+1}): {e}")
            await asyncio.sleep(2)

    # Пробуем unban
    try:
        await bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        await asyncio.sleep(2)
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status == "member":
            return True
    except Exception as e:
        logging.error(f"[ERROR] Unban не помог: {e}")

    return False


# Отправка капчи
async def send_captcha(bot, update: types.Message | types.ChatMemberUpdated, user_id: int, chat_id: int, state):
    logging.info(f"[CAPTCHA] Запрос отправки капчи user={user_id} chat={chat_id}")

    # Проверяем: включены ли стоп-слова
    if not db.have_stop_words(chat_id):
        return

    # Проверяем права бота
    if not await check_bot_permissions(bot, chat_id):
        try:
            if isinstance(update, types.Message):
                await update.answer("Боту не хватает прав для капчи.")
        except:
            pass
        return

    # 🔥 Проверяем: пользователь всё ещё в чате!
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in ["left", "kicked", "banned"]:
            logging.info(
                f"[CAPTCHA] Пользователь {user_id} уже не в чате {chat_id}. Капча НЕ отправляется."
            )
            return
    except Exception as e:
        logging.error(f"[ERROR] Не удалось получить статус пользователя: {e}")
        return

    # Имя пользователя
    try:
        username = update.from_user.username or update.from_user.first_name or "пользователь"
    except:
        username = "пользователь"

    # Генерация капчи
    question, correct_answer = generate_captcha()

    # Увеличиваем попытки (только здесь! НЕ ДВА РАЗА)
    attempts = db.increment_captcha_attempts(user_id, chat_id)
    attempts_left = 3 - attempts

    try:
        # Отправляем капчу
        captcha_message = await bot.send_message(
            chat_id,
            f"@{username}, пройдите капчу, чтобы писать в чат:\n"
            f"{question}\n"
            f"Осталось попыток: {attempts_left}\n"
            f"Капча исчезнет через {db.get_captcha_timeout(chat_id)} секунд.",
            reply_markup=get_captcha_keyboard(correct_answer, chat_id, user_id)
        )

        db.update_captcha_message_id(user_id, chat_id, captcha_message.message_id)
        await state.update_data(captcha_message_id=captcha_message.message_id)

        # Ограничиваем пользователя
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=types.ChatPermissions(can_send_messages=False)
        )

        # Автоудаление по таймауту
        async def timeout_task():
            await asyncio.sleep(db.get_captcha_timeout(chat_id))

            # Если капча не пройдена — бан
            if not db.check_captcha_status(user_id, chat_id):
                try:
                    await bot.delete_message(chat_id, captcha_message.message_id)
                except:
                    pass

                try:
                    await bot.ban_chat_member(
                        chat_id,
                        user_id,
                        until_date=int((datetime.now() + timedelta(hours=24)).timestamp())
                    )
                    ban_msg = await bot.send_message(
                        chat_id, f"@{username} забанен на 24 часа за непрохождение капчи."
                    )
                    await asyncio.sleep(10)
                    await bot.delete_message(chat_id, ban_msg.message_id)
                except Exception as e:
                    logging.error(f"[ERROR] Ошибка при бане: {e}")

                db.delete_captcha_status(user_id, chat_id)

        asyncio.create_task(timeout_task())

    except Exception as e:
        logging.error(f"[ERROR] Ошибка отправки капчи: {e}")