import asyncio
import logging
import re

from aiogram import types
from aiogram.dispatcher import FSMContext

import database
from pin_states import PinStates
import keyboards
from utils import check_bot_permissions

db = database.MainDb()
tasks = []  # глобальный список задач автопостинга


# ===================== Начало автопостинга =====================
async def joined_autoposting(message: types.Message):
    await PinStates.enter_message_1.set()
    await message.answer("Отправьте сообщение, которое вы хотите постить с интервалом")


# ===================== Получаем сообщение =====================
async def got_message_autoposting(message: types.Message, state: FSMContext):
    await state.update_data(message=message, autoposting=True)
    await PinStates.choose_action.set()
    await message.answer("Выберите действие", reply_markup=keyboards.in_autoposting())


# ===================== Список автопостингов =====================
async def autoposting_list(message: types.Message):
    global tasks
    args = message.text.split()
    if len(args) > 1:
        try:
            num = int(args[1]) - 1
            if 0 <= num < len(tasks):
                tasks[num].cancel()
                tasks.pop(num)
                await message.answer("Задача автопостинга удалена.")
                return
        except:
            pass

    text = "/autoposting_list номер — удалить задачу\n\nАктивные задачи:\n"
    if not tasks:
        text += "Нет активных задач."
    else:
        for i, task in enumerate(tasks, 1):
            name = task.get_name() if hasattr(task, 'get_name') and task.get_name() else "Без имени"
            text += f"[{i}] {name}\n"
    await message.answer(text)


# ===================== Удаление последнего автопостинга =====================
async def autoposting_del(message: types.Message):
    global tasks
    if tasks:
        tasks[-1].cancel()
        tasks.pop(-1)
        await message.answer("Последняя задача автопостинга отменена.")
    else:
        await message.answer("Нет задач для отмены.")


# ===================== Выключение всех автопостингов =====================
async def autoposting_off(message: types.Message):
    global tasks
    while tasks:
        task = tasks.pop(0)
        task.cancel()
    await message.answer("Все задачи автопостинга отключены.")


# ===================== Запуск автопостинга =====================
async def start_autoposting(call: types.CallbackQuery, state: FSMContext):
    global tasks
    data = await state.get_data()
    message = data.get('message')
    keyboard = data.get('keyboard')
    interval = data.get('interval')
    chates = data.get('chates')

    if not interval:
        await call.answer("Сначала выберите интервал!", show_alert=True)
        return

    name = (message.text or message.caption or "Автопостинг")[:20]
    task = asyncio.create_task(scheduled_sender(data))
    task.set_name(name)
    tasks.append(task)

    await call.message.edit_text(f"Автопостинг запущен с интервалом {interval} ч.")
    await state.finish()
    logging.info(f"Автопостинг запущен: {name}, интервал {interval} ч.")


# ===================== Колбэки: Интервал =====================
async def delete_interval(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(interval=None)
    data = await state.get_data()
    has_keyboard = bool(data.get('keyboard'))
    has_chates = bool(data.get('chates'))
    kb = keyboards.in_autoposting(has_keyboard=has_keyboard, has_interval=False, has_chates=has_chates)
    await call.message.edit_text("Интервал удалён", reply_markup=kb)


async def add_interval(call: types.CallbackQuery, state: FSMContext):
    await PinStates.interval_add.set()
    await call.message.edit_text("Выберите интервал", reply_markup=keyboards.in_interval_adding())


async def added_interval(call: types.CallbackQuery, state: FSMContext):
    try:
        interval_str = call.data.split('.')[1]
        interval = 1/60 if interval_str == '7' else int(interval_str)  # 7 — раз в минуту
    except:
        interval = 1
    await state.update_data(interval=interval)
    data = await state.get_data()
    has_keyboard = bool(data.get('keyboard'))
    has_chates = bool(data.get('chates'))
    kb = keyboards.in_autoposting(has_keyboard=has_keyboard, has_interval=True, has_chates=has_chates)
    await call.message.edit_text("Интервал добавлен", reply_markup=kb)
    await PinStates.choose_action.set()


# ===================== Колбэки: Кнопки =====================
async def delete_buttons(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(keyboard=None)
    data = await state.get_data()
    has_interval = bool(data.get('interval'))
    has_chates = bool(data.get('chates'))
    kb = keyboards.in_autoposting(has_interval=has_interval, has_chates=has_chates)
    await call.message.edit_text("Кнопки удалены", reply_markup=kb)


async def add_keyboard_button(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("Введите текст кнопки")
    await PinStates.enter_button_text.set()


async def enter_button_text(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await message.answer("Теперь введите ссылку для кнопки")
    await PinStates.enter_button_link.set()


async def enter_button_link(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if re.match(r'^(http|https)://', url):
        data = await state.get_data()
        text = data.get('button_text')
        if data.get('keyboard'):
            kb = data['keyboard']
            kb.add(types.InlineKeyboardButton(text=text, url=url))
        else:
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(text=text, url=url))
        await state.update_data(keyboard=kb)
        has_interval = bool(data.get('interval'))
        has_chates = bool(data.get('chates'))
        reply_kb = keyboards.in_autoposting(has_keyboard=True, has_interval=has_interval, has_chates=has_chates)
        await message.answer("Кнопка добавлена", reply_markup=reply_kb)
        await PinStates.choose_action.set()
    else:
        await message.answer("Некорректная ссылка. Попробуйте ещё раз.")
        await PinStates.enter_button_link.set()


# ===================== Колбэки: Выбор чатов =====================
async def choose_chats(call: types.CallbackQuery, state: FSMContext):
    await PinStates.chates.set()
    await call.message.edit_text('Введите ссылки на чаты через запятую (или оставьте пустым для всех чатов в базе):\n'
                                 'Пример: t.me/chat1, https://t.me/chat2')


async def select_chats(message: types.Message, state: FSMContext):
    await state.update_data(chates=message.text.strip() or None)
    data = await state.get_data()
    has_keyboard = bool(data.get('keyboard'))
    has_interval = bool(data.get('interval'))
    kb = keyboards.in_autoposting(has_keyboard=has_keyboard, has_interval=has_interval, has_chates=True)
    await message.answer("Чаты сохранены", reply_markup=kb)
    await PinStates.choose_action.set()


# ===================== Отправщик сообщений =====================
async def scheduled_sender(data):
    message = data.get('message')
    keyboard = data.get('keyboard')
    interval = data.get('interval') or 1
    chates = data.get('chates')

    entities = message.entities or message.caption_entities or []

    while True:
        try:
            if chates:
                chat_list = [c.strip().replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').lstrip('@') for c in chates.split(',')]
                for chat in chat_list:
                    await send_to_chat(chat, message, keyboard, entities)
            else:
                for chat in db.get_all_chats():
                    if chat[1] == 0:  # has_autoposting
                        continue
                    await send_to_chat(chat[0], message, keyboard, entities)
        except Exception as e:
            logging.error(f"Ошибка в автопостинге: {e}")

        await asyncio.sleep(interval * 3600)


async def send_to_chat(chat_id, original, keyboard, entities):
    try:
        if isinstance(chat_id, str) and not chat_id.isdigit():
            chat_id = '@' + chat_id

        if original.photo:
            await original.bot.send_photo(chat_id, original.photo[-1].file_id,
                                          caption=original.caption or original.text,
                                          reply_markup=keyboard, caption_entities=entities)
        elif original.video:
            await original.bot.send_video(chat_id, original.video.file_id, caption=original.caption,
                                          reply_markup=keyboard)
        elif original.document:
            await original.bot.send_document(chat_id, original.document.file_id, caption=original.caption,
                                              reply_markup=keyboard)
        else:
            await original.bot.send_message(chat_id, original.text or original.caption,
                                            reply_markup=keyboard, entities=entities)
        await asyncio.sleep(1)
    except Exception as e:
        logging.error(f"Не удалось отправить в {chat_id}: {e}")


# ===================== Регистрация хэндлеров =====================
def register_autoposting_handlers(dp):
    dp.register_message_handler(joined_autoposting, commands=['autoposting'])
    dp.register_message_handler(got_message_autoposting, content_types=types.ContentType.ANY, state=PinStates.enter_message_1)

    dp.register_message_handler(autoposting_list, commands=['autoposting_list'])
    dp.register_message_handler(autoposting_del, commands=['autoposting_del'])
    dp.register_message_handler(autoposting_off, commands=['autoposting_off'])

    dp.register_callback_query_handler(start_autoposting, text="start_autoposting", state=PinStates.choose_action)

    dp.register_callback_query_handler(delete_interval, text="delete_interval", state="*")
    dp.register_callback_query_handler(add_interval, text="add_interval", state="*")
    dp.register_callback_query_handler(added_interval, text_contains="add_interval.", state=PinStates.interval_add)

    dp.register_callback_query_handler(delete_buttons, text="delete_buttons", state="*")
    dp.register_callback_query_handler(add_keyboard_button, text="add_keyboard_button", state=PinStates.choose_action)

    dp.register_message_handler(enter_button_text, state=PinStates.enter_button_text)
    dp.register_message_handler(enter_button_link, state=PinStates.enter_button_link)

    dp.register_callback_query_handler(choose_chats, text="choose_chates", state="*")
    dp.register_message_handler(select_chats, state=PinStates.chates)