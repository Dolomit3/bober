from aiogram import Dispatcher

from .admin import register_admin_handlers
from .pin import register_pin_handlers
from .autoposting import register_autoposting_handlers
from .common import register_common_handlers

def register_all(dp: Dispatcher):
    register_admin_handlers(dp)       # сначала все команды, которые должны работать в группах
    register_pin_handlers(dp)
    register_autoposting_handlers(dp)
    register_common_handlers(dp)      # в конце — универсальный обработчик сообщений