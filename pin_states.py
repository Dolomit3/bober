from aiogram.dispatcher.filters.state import StatesGroup, State

class PinStates(StatesGroup):
    # ==================== Для /pin ====================
    enter_message = State()       # Получение сообщения для закрепления
    choose_action = State()       # Выбор действия после отправки сообщения
    interval_add = State()        # Установка интервала (для автопостинга)
    enter_button_text = State()   # Ввод текста кнопки
    enter_button_link = State()   # Ввод ссылки кнопки
    chates = State()              # Выбор чатов для автопостинга

    # ==================== Для /autoposting ====================
    enter_message_1 = State()     # Получение сообщения для автопостинга