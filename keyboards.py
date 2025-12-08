from aiogram import types
import random

# ===================== Главное меню =====================
def main_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(text="📌 Закрепить сообщение", callback_data="menu_pin"),
        types.InlineKeyboardButton(text="📝 Автопостинг", callback_data="menu_autoposting")
    )
    return keyboard

# ===================== Сообщение для отправки/пин =====================
def in_message_sending(has_keyboard=False, has_interval=False):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Закрепить сообщение",
                                            callback_data="send_and_pin_message"))
    if has_keyboard:
        keyboard.add(types.InlineKeyboardButton(text="Добавить ещё кнопку",
                                                callback_data="add_keyboard_button"))
        keyboard.add(types.InlineKeyboardButton(text="Удалить кнопки",
                                                callback_data="delete_buttons"))
    else:
        keyboard.add(types.InlineKeyboardButton(text="Добавить кнопку",
                                                callback_data="add_keyboard_button"))
    if has_interval:
        keyboard.add(types.InlineKeyboardButton(text="Убрать интервал",
                                                callback_data="delete_interval"))
    else:
        keyboard.add(types.InlineKeyboardButton(text="Добавить интервал отправки",
                                                callback_data="add_interval"))
    keyboard.add(types.InlineKeyboardButton(text="Отменить", callback_data="cancel_sending"))
    return keyboard

# ===================== Капча =====================
def get_captcha_keyboard(correct_answer: int, chat_id: int, user_id: int):
    keyboard = types.InlineKeyboardMarkup(row_width=4)
    answers = [correct_answer, correct_answer + 1, correct_answer - 1, correct_answer + 2]
    random.shuffle(answers)
    for ans in answers:
        keyboard.insert(types.InlineKeyboardButton(
            str(ans),
            callback_data=f"captcha_{ans}_{chat_id}_{user_id}"
        ))
    return keyboard

# ===================== Автопостинг =====================
def in_autoposting(has_keyboard=False, has_interval=False, has_chats=False):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="Начать автопостинг", callback_data="start_autoposting"))

    if has_chats:
        keyboard.add(types.InlineKeyboardButton(text='Чаты выбраны', callback_data='chats_chosen'))
    else:
        keyboard.add(types.InlineKeyboardButton(text='Выбрать чаты', callback_data='choose_chats'))

    if has_keyboard:
        keyboard.add(types.InlineKeyboardButton(text="Добавить ещё кнопку", callback_data="add_keyboard_button"))
        keyboard.add(types.InlineKeyboardButton(text="Удалить кнопки", callback_data="delete_buttons"))
    else:
        keyboard.add(types.InlineKeyboardButton(text="Добавить кнопку", callback_data="add_keyboard_button"))

    if has_interval:
        keyboard.add(types.InlineKeyboardButton(text="Убрать интервал", callback_data="delete_interval"))
    else:
        keyboard.add(types.InlineKeyboardButton(text="Добавить интервал", callback_data="add_interval"))

    keyboard.add(types.InlineKeyboardButton(text="Отменить", callback_data="cancel_sending"))
    return keyboard

# ===================== Интервалы =====================
def in_interval_adding():
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    intervals = [("1 минута", 7), ("1 час", 1), ("2 часа", 2), ("3 часа", 3), ("4 часа", 4), ("6 часов", 6)]
    for text, cb in intervals:
        keyboard.insert(types.InlineKeyboardButton(text=text, callback_data=f"add_interval.{cb}"))
    return keyboard