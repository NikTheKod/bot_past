import asyncio
import logging
import os
import csv
import re
import json
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from typing import Dict
from bs4 import BeautifulSoup

# --- КОНФИГ ---
BOT_TOKEN = "8307763743:AAGt5tZAnzu8inHZse5X_N1dw-fIN9Ek1fU"
ADMIN_IDS = [8444790051]
CRYPTO_WALLET = "UQDwD5okkERUN_pl-trSFiAEVMVOgm35Q2choki984WdyRY4"
REQUEST_COEFFICIENT = 1.2

logging.basicConfig(level=logging.INFO)

# --- СОСТОЯНИЯ ---
class TicketStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()

class ParsingStates(StatesGroup):
    waiting_for_requests = State()
    waiting_for_payment_confirmation = State()  # Ждём подтверждения оплаты админом
    waiting_for_query = State()
    waiting_for_limit = State()

# --- ПЕРЕВОДЫ ---
translations = {
    'ru': {
        'welcome': "🇷🇺 Добро пожаловать в ParsTape!",
        'lang_selected': "Язык: русский 🇷🇺",
        'main_menu_text': "📊 *ParsTape — парсинг маркетплейсов*\n\n"
                          "🟢 Wildberries и Ozon\n"
                          "🤖 Автоматический сбор данных\n"
                          "📈 Удобные отчёты",
        'parsing_info': "🕸️ *Парсинг*\n\n💰 1 запрос = 1.2 ₽\n⭐ 1 звезда = 1.2 ₽\n\nВведите количество запросов:",
        'enter_requests': "🔢 Введите количество запросов (1-10000):",
        'price_calculation': "📊 *Заказ:*\n• Запросов: {requests}\n• Сумма: {price:.2f} ₽\n• Звёзд: {stars:.1f} ⭐\n\nНажмите «Оплатить»",
        'parsing_start': "🔍 Введите поисковый запрос (например: iphone, наушники):",
        'parsing_limit': "📊 Введите количество товаров (1-50):",
        'parsing_in_progress': "🔄 Парсинг...\nПодождите 10-30 секунд",
        'parsing_complete': "✅ *Готово!*",
        'parsing_error': "❌ Ошибка. Попробуйте другой запрос",
        'free_for_admin': "👑 Админ — бесплатно!\nВведите запрос:",
        'payment_required': "💳 *Оплата {price:.2f} ₽*\n\nКошелёк:\n`{wallet}`\n\nПосле оплаты нажмите «Я оплатил»",
        'payment_not_needed': "✅ Введите поисковый запрос:",
        'invalid_number': "❌ Введите число от 1 до 10000",
        'invalid_limit': "❌ Введите число от 1 до 50",
        'settings': "⚙️ Настройки",
        'support': "🆘 Поддержка",
        'parsing': "🕸️ Парсинг",
        'settings_text': "Настройки",
        'change_lang': "🌐 Язык",
        'back': "◀️ Назад",
        'menu': "🏠 Меню",
        'pay': "💳 Оплатить",
        'i_paid': "✅ Я оплатил",
        'create_ticket': "📝 Тикет",
        'enter_title': "Тема:",
        'enter_description': "Описание:",
        'ticket_sent': "✅ Тикет отправлен!",
        'cancel': "❌ Отмена",
        'ticket_created_notify': "📩 Новый тикет от {name}\nТема: {title}\n{desc}",
        'ticket_closed': "✅ Тикет закрыт",
        'no_active_tickets': "Нет тикетов",
        'unknown_command': "❌ Неизвестная команда",
        'waiting_payment': "⏳ Ожидаем подтверждения оплаты от админа",
        'payment_confirmed': "✅ Оплата подтверждена! Введите запрос:",
    },
    'en': {
        'welcome': "🇬🇧 Welcome to ParsTape!",
        'lang_selected': "Language: English",
        'main_menu_text': "📊 *ParsTape — Marketplace Parser*\n\nWB & Ozon data",
        'parsing_info': "🕸️ *Parsing*\n\n💰 1 request = 1.2 ₽\nEnter requests count:",
        'enter_requests': "🔢 Enter requests count (1-10000):",
        'price_calculation': "📊 *Order:*\n• Requests: {requests}\n• Price: {price:.2f} ₽\n• Stars: {stars:.1f} ⭐\n\nClick 'Pay'",
        'parsing_start': "🔍 Enter search query:",
        'parsing_limit': "📊 Enter items count (1-50):",
        'parsing_in_progress': "🔄 Parsing...",
        'parsing_complete': "✅ *Done!*",
        'parsing_error': "❌ Error. Try again",
        'free_for_admin': "👑 Admin - free!\nEnter query:",
        'payment_required': "💳 *Pay {price:.2f} ₽*\n\nWallet:\n`{wallet}`\n\nClick 'I paid' after sending",
        'payment_not_needed': "✅ Enter search query:",
        'invalid_number': "❌ Enter 1-10000",
        'invalid_limit': "❌ Enter 1-50",
        'settings': "⚙️ Settings",
        'support': "🆘 Support",
        'parsing': "🕸️ Parsing",
        'settings_text': "Settings",
        'change_lang': "🌐 Language",
        'back': "◀️ Back",
        'menu': "🏠 Menu",
        'pay': "💳 Pay",
        'i_paid': "✅ I paid",
        'create_ticket': "📝 Ticket",
        'enter_title': "Title:",
        'enter_description': "Description:",
        'ticket_sent': "✅ Ticket sent!",
        'cancel': "❌ Cancel",
        'ticket_created_notify': "📩 New ticket from {name}\nTitle: {title}\n{desc}",
        'ticket_closed': "✅ Ticket closed",
        'no_active_tickets': "No tickets",
        'unknown_command': "❌ Unknown command",
        'waiting_payment': "⏳ Waiting for admin confirmation",
        'payment_confirmed': "✅ Payment confirmed! Enter query:",
    }
}

user_lang: Dict[int, str] = {}
active_tickets: Dict[int, dict] = {}
pending_payments: Dict[int, dict] = {}  # Ожидание подтверждения оплаты
parsed_files: Dict[int, dict] = {}

# ==================== ПАРСЕР ====================
class ParsTape:
    async def search_wildberries(self, query, limit):
        products = []
        try:
            # API Wildberries
            url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?appType=1&curr=rub&dest=-1257786&query={query}&resultset=catalog&sort=popular&spp=30&limit={limit}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if 'data' in data and 'products' in data['data']:
                            for p in data['data']['products'][:limit]:
                                name = p.get('name', '')
                                price = p.get('priceU', 0) / 100
                                link = f"https://www.wildberries.ru/catalog/{p.get('id')}/detail.aspx"
                                if name and price > 0:
                                    products.append({'name': name[:80], 'price': int(price), 'link': link})
                    else:
                        print(f"WB status: {resp.status}")
        except Exception as e:
            print(f"WB error: {e}")
        return products
    
    async def search_ozon(self, query, limit):
        products = []
        try:
            url = f"https://www.ozon.ru/search/?text={query}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, 'lxml')
                        
                        # Ищем карточки
                        for card in soup.find_all('a', href=re.compile(r'/product/'))[:limit*2]:
                            try:
                                name_elem = card.find('span', class_=re.compile(r'tsBodyM|tile-title'))
                                name = name_elem.get_text(strip=True) if name_elem else ''
                                
                                price_elem = card.find('span', class_=re.compile(r'price|final'))
                                price = 0
                                if price_elem:
                                    price_text = price_elem.get_text(strip=True)
                                    nums = re.findall(r'(\d[\d\s]*)', price_text)
                                    if nums:
                                        price = int(re.sub(r'\s', '', nums[0]))
                                
                                if name and price > 0 and len(products) < limit:
                                    href = card.get('href', '')
                                    link = f"https://www.ozon.ru{href}" if href.startswith('/') else href
                                    products.append({'name': name[:80], 'price': price, 'link': link})
                            except:
                                continue
                    else:
                        print(f"Ozon status: {resp.status}")
        except Exception as e:
            print(f"Ozon error: {e}")
        return products
    
    async def search_both(self, query, limit):
        print(f"🔍 Поиск: {query}, лимит: {limit}")
        
        wb = await self.search_wildberries(query, limit)
        print(f"WB: {len(wb)} товаров")
        
        await asyncio.sleep(1)
        
        ozon = await self.search_ozon(query, limit)
        print(f"Ozon: {len(ozon)} товаров")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = re.sub(r'[^\w\s-]', '', query).replace(' ', '_')
        files = {}
        
        # Сводка
        summary_file = f"ParsTape_Summary_{safe_query}_{timestamp}.csv"
        with open(summary_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['query', 'wb_count', 'ozon_count', 'total', 'timestamp'])
            writer.writerow([query, len(wb), len(ozon), len(wb)+len(ozon), timestamp])
        files['summary'] = summary_file
        
        # WB
        if wb:
            wb_file = f"ParsTape_WB_{safe_query}_{timestamp}.csv"
            with open(wb_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['number', 'name', 'price', 'link'])
                for i, p in enumerate(wb, 1):
                    writer.writerow([i, p['name'], p['price'], p['link']])
            files['wb'] = wb_file
        
        # Ozon
        if ozon:
            ozon_file = f"ParsTape_Ozon_{safe_query}_{timestamp}.csv"
            with open(ozon_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['number', 'name', 'price', 'link'])
                for i, p in enumerate(ozon, 1):
                    writer.writerow([i, p['name'], p['price'], p['link']])
            files['ozon'] = ozon_file
        
        return files, wb, ozon

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard(lang):
    kb = [[types.KeyboardButton(text=translations[lang]['settings'])],
          [types.KeyboardButton(text=translations[lang]['support'])],
          [types.KeyboardButton(text=translations[lang]['parsing'])]]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard(lang):
    return types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text=translations[lang]['back'])]], resize_keyboard=True)

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def get_payment_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['pay'], callback_data="pay_order")],
        [InlineKeyboardButton(text=translations[lang]['back'], callback_data="back_to_main")]
    ])

def get_i_paid_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['i_paid'], callback_data="i_paid")],
        [InlineKeyboardButton(text=translations[lang]['back'], callback_data="back_to_main")]
    ])

def get_support_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['create_ticket'], callback_data="create_ticket")],
        [InlineKeyboardButton(text=translations[lang]['back'], callback_data="back_to_main")]
    ])

def get_cancel_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['cancel'], callback_data="cancel_ticket")]
    ])

def get_settings_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['change_lang'], callback_data="change_lang")],
        [InlineKeyboardButton(text=translations[lang]['back'], callback_data="back_to_main")]
    ])

# ==================== ФУНКЦИИ ====================
def calculate_price(requests_count: int):
    price = requests_count * REQUEST_COEFFICIENT
    return price, price

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== ХЭНДЛЕРЫ ====================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🌍 Выберите язык:", reply_markup=get_lang_keyboard())

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language(callback: CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_lang[callback.from_user.id] = lang_code
    await callback.message.delete()
    await callback.message.answer(translations[lang_code]['main_menu_text'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang_code))
    await callback.answer()

@dp.message(F.text.in_({'🏠 Меню', '🏠 Menu'}))
@dp.message(F.text.in_({'◀️ Назад', '◀️ Back'}))
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(event, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    lang = user_lang.get(user_id, 'ru')
    if isinstance(event, CallbackQuery):
        await event.message.delete()
        await event.message.answer(translations[lang]['main_menu_text'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))
        await event.answer()
    else:
        await event.answer(translations[lang]['main_menu_text'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))

@dp.message(F.text.in_({'🕸️ Парсинг', '🕸️ Parsing'}))
async def parsing_menu(message: Message, state: FSMContext):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(translations[lang]['parsing_info'], parse_mode="Markdown", reply_markup=get_back_keyboard(lang))
    await message.answer(translations[lang]['enter_requests'])
    await state.set_state(ParsingStates.waiting_for_requests)

@dp.message(ParsingStates.waiting_for_requests)
async def get_requests_count(message: Message, state: FSMContext):
    lang = user_lang.get(message.from_user.id, 'ru')
    try:
        count = int(message.text)
        if count < 1 or count > 10000:
            await message.answer(translations[lang]['invalid_number'])
            return
        price, stars = calculate_price(count)
        await state.update_data(requests=count, price=price)
        text = translations[lang]['price_calculation'].format(requests=count, price=price, stars=stars)
        await message.answer(text, parse_mode="Markdown", reply_markup=get_payment_keyboard(lang))
    except ValueError:
        await message.answer(translations[lang]['invalid_number'])

@dp.callback_query(lambda c: c.data == "pay_order")
async def process_payment(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    data = await state.get_data()
    
    if user_id in ADMIN_IDS:
        await callback.message.edit_text(translations[lang]['free_for_admin'])
        await callback.message.answer(translations[lang]['parsing_start'])
        await state.set_state(ParsingStates.waiting_for_query)
    else:
        price = data.get('price', 0)
        text = translations[lang]['payment_required'].format(price=price, wallet=CRYPTO_WALLET)
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_i_paid_keyboard(lang))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "i_paid")
async def i_paid(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    data = await state.get_data()
    
    # Отправляем админу запрос на подтверждение
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"💰 *ЗАПРОС ПОДТВЕРЖДЕНИЯ ОПЛАТЫ*\n\n"
            f"👤 Пользователь: {callback.from_user.full_name}\n"
            f"🆔 ID: {user_id}\n"
            f"📊 Запросов: {data.get('requests', 0)}\n"
            f"💰 Сумма: {data.get('price', 0):.2f} ₽\n\n"
            f"✅ /confirm_payment {user_id} - подтвердить\n"
            f"❌ /reject_payment {user_id} - отклонить",
            parse_mode="Markdown"
        )
    
    await callback.message.edit_text(translations[lang]['waiting_payment'])
    await state.set_state(ParsingStates.waiting_for_payment_confirmation)
    await callback.answer()

@dp.message(Command("confirm_payment"))
async def confirm_payment(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /confirm_payment USER_ID")
        return
    try:
        user_id = int(parts[1])
        lang = user_lang.get(user_id, 'ru')
        
        # Уведомляем пользователя
        await bot.send_message(user_id, translations[lang]['payment_confirmed'])
        await bot.send_message(user_id, translations[lang]['parsing_start'])
        
        # Устанавливаем состояние для пользователя
        await state.set_state(ParsingStates.waiting_for_query)
        
        # Сохраняем в state пользователя (нужен отдельный FSMContext)
        # Для этого отправим сообщение от имени бота с установкой состояния
        await message.answer(f"✅ Оплата пользователя {user_id} подтверждена. Он может ввести запрос.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(Command("reject_payment"))
async def reject_payment(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /reject_payment USER_ID")
        return
    try:
        user_id = int(parts[1])
        lang = user_lang.get(user_id, 'ru')
        await bot.send_message(user_id, "❌ Ваша оплата не подтверждена. Пожалуйста, свяжитесь с поддержкой.")
        await message.answer(f"❌ Оплата пользователя {user_id} отклонена")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(ParsingStates.waiting_for_query)
async def get_search_query(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    query = message.text.strip()
    await state.update_data(query=query)
    await message.answer(translations[lang]['parsing_limit'])
    await state.set_state(ParsingStates.waiting_for_limit)

@dp.message(ParsingStates.waiting_for_limit)
async def get_limit_and_parse(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    
    try:
        limit = int(message.text)
        if limit < 1 or limit > 50:
            await message.answer(translations[lang]['invalid_limit'])
            return
        
        data = await state.get_data()
        query = data.get('query', '')
        
        wait_msg = await message.answer(translations[lang]['parsing_in_progress'])
        
        parser = ParsTape()
        files, wb_products, ozon_products = await parser.search_both(query, limit)
        
        await wait_msg.delete()
        
        if not wb_products and not ozon_products:
            await message.answer("❌ Ничего не найдено. Попробуйте другой запрос.")
        else:
            await message.answer(translations[lang]['parsing_complete'])
            
            if wb_products:
                await message.answer_document(FSInputFile(files['wb']), caption=f"📊 Wildberries: {len(wb_products)} товаров")
            else:
                await message.answer("❌ Wildberries: ничего не найдено")
            
            if ozon_products:
                await message.answer_document(FSInputFile(files['ozon']), caption=f"📊 Ozon: {len(ozon_products)} товаров")
            else:
                await message.answer("❌ Ozon: ничего не найдено")
            
            if 'summary' in files:
                await message.answer_document(FSInputFile(files['summary']), caption="📈 Сводка")
        
        await message.answer(translations[lang]['main_menu_text'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))
        await state.clear()
        
    except ValueError:
        await message.answer(translations[lang]['invalid_limit'])
    except Exception as e:
        logging.error(f"Parse error: {e}")
        await message.answer(translations[lang]['parsing_error'])

@dp.message(F.text.in_({'⚙️ Настройки', '⚙️ Settings'}))
async def settings_menu(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(translations[lang]['settings_text'], reply_markup=get_settings_keyboard(lang))

@dp.callback_query(lambda c: c.data == "change_lang")
async def change_lang(callback: CallbackQuery):
    await callback.message.edit_text("🌍 Выберите язык:", reply_markup=get_lang_keyboard())
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
    await callback.message.answer(translations[lang]['main_menu_text'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))
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

    active_tickets[user_id] = {'title': title, 'description': desc}
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, translations[lang]['ticket_created_notify'].format(name=name, title=title, desc=desc) + f"\n\n/reply {user_id} [текст]\n/close_ticket_admin {user_id}")
    
    await message.answer(translations[lang]['ticket_sent'], reply_markup=get_main_keyboard(lang))
    await state.clear()

@dp.message(Command("reply"))
async def admin_reply(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("/reply USER_ID ТЕКСТ")
        return
    try:
        user_id = int(parts[1])
        reply_text = parts[2]
        await bot.send_message(user_id, f"✉️ *Ответ поддержки:*\n{reply_text}\n\n/close_ticket", parse_mode="Markdown")
        await message.answer(f"✅ Ответ отправлен")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(Command("close_ticket"))
async def close_ticket(message: Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    if user_id in active_tickets:
        del active_tickets[user_id]
        await message.answer(translations[lang]['ticket_closed'])
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"📌 Тикет от {user_id} закрыт")
    else:
        await message.answer(translations[lang]['no_active_tickets'])

@dp.message(Command("close_ticket_admin"))
async def close_ticket_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("/close_ticket_admin USER_ID")
        return
    try:
        user_id = int(parts[1])
        if user_id in active_tickets:
            del active_tickets[user_id]
            await message.answer(f"✅ Тикет {user_id} закрыт")
            await bot.send_message(user_id, "🔒 Тикет закрыт администратором")
        else:
            await message.answer("Тикет не найден")
    except:
        await message.answer("Ошибка")

@dp.message(Command("admin"))
async def admin_check(message: Message):
    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        await message.answer(f"✅ *Администратор*\n\n📊 Тикетов: {len(active_tickets)}\n💰 Ожидают оплату: {len(pending_payments)}", parse_mode="Markdown")
    else:
        await message.answer(f"❌ Вы не админ. ID: {user_id}")

@dp.message()
async def unknown_command(message: Message, state: FSMContext):
    if not await state.get_state():
        lang = user_lang.get(message.from_user.id, 'ru')
        await message.answer(translations[lang]['unknown_command'], reply_markup=get_main_keyboard(lang))

async def main():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
