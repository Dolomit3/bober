from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMINS_ID
import database
from utils import send_captcha
from pin_states import PinStates

db = database.MainDb()


# ================== Главное меню ==================
def main_menu(is_admin=False):
    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton("Закрепить сообщение", callback_data="menu_pin"),
        InlineKeyboardButton("Открепить все", callback_data="menu_unpin")
    )
    kb.add(
        InlineKeyboardButton("Автопостинг", callback_data="menu_autoposting"),
        InlineKeyboardButton("Список автопостинга", callback_data="menu_autoposting_list")
    )
    kb.add(
        InlineKeyboardButton("Пройти капчу", callback_data="menu_captcha")
    )

    if is_admin:
        kb.add(
            InlineKeyboardButton("Добавить чат", callback_data="menu_add_chat"),
            InlineKeyboardButton("Удалить чат", callback_data="menu_delete_chat")
        )
        kb.add(
            InlineKeyboardButton("Вкл/Выкл стоп-слова", callback_data="menu_toggle_stopwords"),
            InlineKeyboardButton("Вкл/Выкл закрепление", callback_data="menu_toggle_pinning")
        )
        kb.add(
            InlineKeyboardButton("Вкл/Выкл автопостинг", callback_data="menu_toggle_autoposting"),
            InlineKeyboardButton("Кулдаун сообщений", callback_data="menu_cooldown")
        )

    return kb


# ================== Отображение меню ==================
async def show_main_menu(message: types.Message):
    is_admin = message.from_user.id in ADMINS_ID
    kb = main_menu(is_admin)
    await message.answer("Выберите действие:", reply_markup=kb)


# ================== Колбэки меню ==================
async def menu_callback(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    is_admin = user_id in ADMINS_ID

    if call.data == "menu_pin":
        await PinStates.enter_message.set()
        await call.message.edit_text("Отправьте сообщение, которое хотите закрепить")
    elif call.data == "menu_unpin":
        from handlers.pin import unpin_last_messages
        await unpin_last_messages(call.message)
    elif call.data == "menu_autoposting":
        await PinStates.enter_message_1.set()
        await call.message.edit_text("Отправьте сообщение для автопостинга")
    elif call.data == "menu_autoposting_list":
        from handlers.autoposting import autoposting_list
        await autoposting_list(call.message)
    elif call.data == "menu_captcha":
        await send_captcha(call.bot, call.message, user_id, call.message.chat.id, state)

    # Админские кнопки
    elif is_admin:
        if call.data == "menu_add_chat":
            from handlers.admin import add_chat
            await add_chat(call.message)
        elif call.data == "menu_delete_chat":
            from handlers.admin import delete_chat
            await delete_chat(call.message)
        elif call.data == "menu_toggle_stopwords":
            chat_id = call.message.chat.id
            current = db.get_chat(chat_id)[3]  # has_stopwords
            if current:
                await db.update_chat_settings(chat_id, has_stopwords=0)
                await call.message.edit_text("Стоп-слова и капча выключены")
            else:
                await db.update_chat_settings(chat_id, has_stopwords=1)
                await call.message.edit_text("Стоп-слова и капча включены")
        elif call.data == "menu_toggle_pinning":
            chat_id = call.message.chat.id
            current = db.get_chat(chat_id)[2]  # has_autopining
            if current:
                await db.update_chat_settings(chat_id, has_autopining=0)
                await call.message.edit_text("Закрепление выключено")
            else:
                await db.update_chat_settings(chat_id, has_autopining=1)
                await call.message.edit_text("Закрепление включено")
        elif call.data == "menu_toggle_autoposting":
            chat_id = call.message.chat.id
            current = db.get_chat(chat_id)[1]  # has_autoposting
            if current:
                await db.update_chat_settings(chat_id, has_autoposting=0)
                await call.message.edit_text("Автопостинг выключен")
            else:
                await db.update_chat_settings(chat_id, has_autoposting=1)
                await call.message.edit_text("Автопостинг включён")
        elif call.data == "menu_cooldown":
            await call.message.edit_text("Для изменения кулдауна используйте команду:\n"
                                         "/set_message_cooldown <секунды> [--all]")

    await call.answer()