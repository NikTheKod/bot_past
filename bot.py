import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from typing import Dict

# --- КОНФИГ ---
BOT_TOKEN = "8307763743:AAGt5tZAnzu8inHZse5X_N1dw-fIN9Ek1fU"
ADMIN_IDS = [8444790051]  # Ваш ID админа

logging.basicConfig(level=logging.INFO)

# --- СОСТОЯНИЯ ---
class TicketStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()

# --- ПЕРЕВОДЫ ---
translations = {
    'ru': {
        'welcome': "🇷🇺 Добро пожаловать в ParsTape!\nВаш надёжный парсинг маркетплейсов на заказ.",
        'lang_selected': "Язык установлен: русский 🇷🇺",
        'main_menu': "📋 Главное меню:",
        'settings': "⚙️ Настройки",
        'support': "🆘 Поддержка",
        'parsing': "🕸️ Парсинг",
        'parsing_unavailable': "❌ Парсинг в Telegram пока не работает. Пожалуйста, свяжитесь с поддержкой.",
        'settings_text': "Здесь вы можете изменить язык или просмотреть данные.",
        'change_lang': "🌐 Изменить язык",
        'back': "◀️ Назад",
        'menu': "🏠 Меню",
        'create_ticket': "📝 Создать тикет",
        'enter_title': "Введите название вашего вопроса/проблемы:",
        'enter_description': "Теперь введите подробное описание:",
        'ticket_sent': "✅ Ваш тикет отправлен админам. Ожидайте ответа.",
        'cancel': "❌ Отмена",
        'ticket_created_notify': "📩 Новый тикет от {name}\nНазвание: {title}\nОписание: {desc}",
        'ticket_closed': "✅ Тикет закрыт. Спасибо!",
        'no_active_tickets': "Нет активных тикетов.",
        'unknown_command': "❌ Неизвестная команда. Пожалуйста, используйте кнопки меню.",
    },
    'en': {
        'welcome': "🇬🇧 Welcome to ParsTape!\nYour custom marketplace parsing service.",
        'lang_selected': "Language set: English 🇬🇧",
        'main_menu': "📋 Main menu:",
        'settings': "⚙️ Settings",
        'support': "🆘 Support",
        'parsing': "🕸️ Parsing",
        'parsing_unavailable': "❌ Parsing in Telegram is not working yet. Please contact support.",
        'settings_text': "Here you can change language or view info.",
        'change_lang': "🌐 Change language",
        'back': "◀️ Back",
        'menu': "🏠 Menu",
        'create_ticket': "📝 Create ticket",
        'enter_title': "Enter the title of your issue:",
        'enter_description': "Now enter a detailed description:",
        'ticket_sent': "✅ Your ticket has been sent. Wait for a reply.",
        'cancel': "❌ Cancel",
        'ticket_created_notify': "📩 New ticket from {name}\nTitle: {title}\nDescription: {desc}",
        'ticket_closed': "✅ Ticket closed. Thank you!",
        'no_active_tickets': "No active tickets.",
        'unknown_command': "❌ Unknown command. Please use the menu buttons.",
    }
}

user_lang: Dict[int, str] = {}
active_tickets: Dict[int, dict] = {}

# --- КЛАВИАТУРЫ ---
def get_main_keyboard(lang):
    kb = [
        [types.KeyboardButton(text=translations[lang]['settings'])],
        [types.KeyboardButton(text=translations[lang]['support'])],
        [types.KeyboardButton(text=translations[lang]['parsing'])]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard(lang):
    kb = [
        [types.KeyboardButton(text=translations[lang]['back'])],
        [types.KeyboardButton(text=translations[lang]['menu'])]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_settings_keyboard(lang):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['change_lang'], callback_data="change_lang")],
        [InlineKeyboardButton(text=translations[lang]['back'], callback_data="back_to_main")]
    ])
    return kb

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def get_support_keyboard(lang):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['create_ticket'], callback_data="create_ticket")],
        [InlineKeyboardButton(text=translations[lang]['back'], callback_data="back_to_main")]
    ])
    return kb

def get_cancel_keyboard(lang):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['cancel'], callback_data="cancel_ticket")]
    ])
    return kb

# --- ХЭНДЛЕРЫ ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🌍 Выберите язык / Choose language:", reply_markup=get_lang_keyboard())

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language(callback: CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_lang[callback.from_user.id] = lang_code
    await callback.message.edit_text(translations[lang_code]['lang_selected'])
    await callback.message.answer(translations[lang_code]['welcome'])
    await callback.message.answer(translations[lang_code]['main_menu'], reply_markup=get_main_keyboard(lang_code))
    await callback.answer()

@dp.message(F.text.in_({'◀️ Назад', '◀️ Back'}))
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(event, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    lang = user_lang.get(user_id, 'ru')
    if isinstance(event, CallbackQuery):
        await event.message.delete()
        await event.message.answer(translations[lang]['main_menu'], reply_markup=get_main_keyboard(lang))
        await event.answer()
    else:
        await event.answer(translations[lang]['main_menu'], reply_markup=get_main_keyboard(lang))

# Кнопка Меню
@dp.message(F.text.in_({'🏠 Меню', '🏠 Menu'}))
async def menu_button(message: Message, state: FSMContext):
    await state.clear()
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(translations[lang]['main_menu'], reply_markup=get_main_keyboard(lang))

@dp.message(F.text.in_({'🕸️ Парсинг', '🕸️ Parsing'}))
async def parsing_unavailable(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(translations[lang]['parsing_unavailable'], reply_markup=get_back_keyboard(lang))

@dp.message(F.text.in_({'⚙️ Настройки', '⚙️ Settings'}))
async def settings_menu(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(translations[lang]['settings_text'], reply_markup=get_settings_keyboard(lang))

@dp.callback_query(lambda c: c.data == "change_lang")
async def change_lang(callback: CallbackQuery):
    await callback.message.edit_text("🌍 Выберите язык / Choose language:", reply_markup=get_lang_keyboard())
    await callback.answer()

@dp.message(F.text.in_({'🆘 Поддержка', '🆘 Support'}))
async def support_menu(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer("🛟", reply_markup=get_support_keyboard(lang))

@dp.callback_query(lambda c: c.data == "create_ticket")
async def create_ticket_start(callback: CallbackQuery, state: FSMContext):
    lang = user_lang.get(callback.from_user.id, 'ru')
    await callback.message.answer(translations[lang]['enter_title'], reply_markup=get_cancel_keyboard(lang))
    await state.set_state(TicketStates.waiting_for_title)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_ticket")
async def cancel_ticket(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = user_lang.get(callback.from_user.id, 'ru')
    await callback.message.delete()
    await callback.message.answer(translations[lang]['main_menu'], reply_markup=get_main_keyboard(lang))
    await callback.answer()

@dp.message(TicketStates.waiting_for_title)
async def get_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(translations[lang]['enter_description'], reply_markup=get_cancel_keyboard(lang))
    await state.set_state(TicketStates.waiting_for_description)

@dp.message(TicketStates.waiting_for_description)
async def get_description(message: Message, state: FSMContext):
    data = await state.get_data()
    title = data['title']
    desc = message.text
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    name = message.from_user.full_name

    active_tickets[user_id] = {'title': title, 'description': desc, 'user_id': user_id}

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, 
                translations[lang]['ticket_created_notify'].format(name=name, title=title, desc=desc) +
                f"\n\n💬 Чтобы ответить: /reply {user_id} [текст]"
            )
        except:
            pass

    await message.answer(translations[lang]['ticket_sent'], reply_markup=get_main_keyboard(lang))
    await state.clear()

@dp.message(Command("reply"))
async def admin_reply(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("ℹ️ Использование: /reply USER_ID ТЕКСТ ОТВЕТА")
        return
    try:
        user_id = int(parts[1])
        reply_text = parts[2]
        lang = user_lang.get(user_id, 'ru')
        await bot.send_message(user_id, f"✉️ Ответ поддержки:\n{reply_text}\n\n🔄 Если вопрос решён, нажмите /close_ticket")
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(Command("close_ticket"))
async def close_ticket(message: Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    if user_id in active_tickets:
        del active_tickets[user_id]
        await message.answer(translations[lang]['ticket_closed'])
    else:
        await message.answer(translations[lang]['no_active_tickets'])

@dp.message(Command("admin"))
async def admin_check(message: Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    if user_id in ADMIN_IDS:
        await message.answer(f"✅ Вы администратор! Ваш ID: {user_id}\nАктивных тикетов: {len(active_tickets)}")
    else:
        await message.answer(f"❌ Вы не администратор. Ваш ID: {user_id}")

# Обработчик неизвестных команд (ловушка для всего остального)
@dp.message()
async def unknown_command(message: Message, state: FSMContext):
    # Проверяем, не находится ли пользователь в процессе создания тикета
    current_state = await state.get_state()
    if current_state:
        # Если пользователь в диалоге создания тикета, игнорируем или предупреждаем
        lang = user_lang.get(message.from_user.id, 'ru')
        await message.answer(translations[lang]['unknown_command'])
    else:
        lang = user_lang.get(message.from_user.id, 'ru')
        await message.answer(translations[lang]['unknown_command'], reply_markup=get_main_keyboard(lang))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
