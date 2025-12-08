import asyncio
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

import database
from pin_states import PinStates
import keyboards
from utils import check_bot_permissions

db = database.MainDb()


# ===================== Начало процесса закрепления =====================
async def joined_pin(message: types.Message):
    await PinStates.enter_message.set()
    await message.answer("Отправьте сообщение, которое вы хотите закрепить")


# ===================== Получаем сообщение для закрепления =====================
async def got_message_pin(message: types.Message, state: FSMContext):
    await state.update_data(message=message)
    await PinStates.choose_action.set()
    await message.answer("Выберите действие", reply_markup=keyboards.in_message_sending())


# ===================== Открепление всех сообщений =====================
async def unpin_last_messages(message: types.Message):
    logging.info(f"/unpin от {message.from_user.id} в чате {message.chat.id}")
    try:
        messages = db.get_pinned_messages()
        if not messages:
            await message.answer("Нет закреплённых сообщений.")
            return

        for message_id, chat_id in messages:
            try:
                await message.bot.unpin_chat_message(chat_id, message_id)
                await message.bot.delete_message(chat_id, message_id)
                logging.info(f"Откреплено и удалено {message_id} в {chat_id}")
            except Exception as e:
                logging.error(f"Ошибка открепления {message_id} в {chat_id}: {e}")

        await message.answer("Все закреплённые сообщения откреплены и удалены")
        # db.clear_pinned_messages()  # если есть метод очистки
    except Exception as e:
        logging.error(f"Ошибка /unpin: {e}")
        await message.answer("Ошибка при откреплении.")


# ===================== Колбэк: Отмена отправки =====================
async def cancel_sending(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    try:
        await call.message.delete()
    except:
        pass


# ===================== Колбэк: Отправка и закрепление =====================
async def send_and_pin_message(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    original = data.get('message')
    keyboard = data.get('keyboard')

    messages = []
    chats = db.get_all_chats()

    for chat in chats:
        chat_id = chat[0]
        if chat[2] == 0:  # has_autopining
            continue

        if not await check_bot_permissions(call.bot, chat_id):
            continue

        try:
            if original.photo:
                sent = await call.bot.send_photo(
                    chat_id, original.photo[-1].file_id,
                    caption=original.caption or original.text,
                    reply_markup=keyboard,
                    caption_entities=original.caption_entities or original.entities
                )
            elif original.video:
                sent = await call.bot.send_video(
                    chat_id, original.video.file_id,
                    caption=original.caption,
                    reply_markup=keyboard
                )
            elif original.document:
                sent = await call.bot.send_document(
                    chat_id, original.document.file_id,
                    caption=original.caption,
                    reply_markup=keyboard
                )
            else:
                sent = await call.bot.send_message(
                    chat_id, original.text or original.caption,
                    reply_markup=keyboard,
                    entities=original.entities or original.caption_entities
                )

            messages.append(sent)
            await asyncio.sleep(1)
            await call.bot.pin_chat_message(chat_id, sent.message_id, disable_notification=True)
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Ошибка отправки/закрепления в {chat_id}: {e}")

    # Сохраняем закреплённые сообщения в БД
    for msg in messages:
        try:
            db.insert_pinned_message(msg.message_id, msg.chat.id)
        except:
            pass

    await call.message.edit_text("Сообщение успешно отправлено и закреплено во всех чатах")
    await state.finish()


# ===================== Регистрация хэндлеров =====================
def register_pin_handlers(dp):
    dp.register_message_handler(joined_pin, commands=['pin'])
    dp.register_message_handler(got_message_pin, content_types=types.ContentType.ANY, state=PinStates.enter_message)
    dp.register_message_handler(unpin_last_messages, commands=['unpin'])

    dp.register_callback_query_handler(cancel_sending, text="cancel_sending", state="*")
    dp.register_callback_query_handler(send_and_pin_message, text="send_and_pin_message", state=PinStates.choose_action)