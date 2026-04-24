import asyncio
import logging
import os
import time
import random
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
REQUEST_COEFFICIENT = 1.2  # Коэффициент: 1 запрос = 1.2 звезды

logging.basicConfig(level=logging.INFO)

# --- СОСТОЯНИЯ ---
class TicketStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()

class ParsingStates(StatesGroup):
    waiting_for_requests = State()
    waiting_for_query = State()
    waiting_for_limit = State()

# --- ПЕРЕВОДЫ ---
translations = {
    'ru': {
        'welcome': "🇷🇺 Добро пожаловать в ParsTape!\nВаш надёжный парсинг маркетплейсов на заказ.",
        'lang_selected': "Язык установлен: русский 🇷🇺",
        'main_menu_text': "📊 *ParsTape — ваш эксперт по маркетплейсам*\n\n"
                          "🟢 *Актуальные данные*\n"
                          "Цены и остатки обновляются каждые 15 минут.\n\n"
                          "🤖 *Автоматический парсинг*\n"
                          "Система сама собирает данные с маркетплейсов.\n\n"
                          "📈 *Удобная аналитика*\n"
                          "Графики, таблицы и отчёты.",
        'parsing_info': "🕸️ *Парсинг Wildberries и Ozon*\n\n"
                        "Автоматический сбор и анализ данных.\n\n"
                        "💰 *Цена:* 1 запрос = 1.2 ₽\n"
                        "⭐ *1 звезда = 1.2 ₽*\n\n"
                        "📝 Введите количество запросов:",
        'enter_requests': "🔢 Введите количество запросов:",
        'price_calculation': "📊 *Ваш заказ:*\n"
                             "• Запросов: {requests} шт.\n"
                             "• Стоимость: {price:.2f} ₽\n"
                             "• Звёзд: {stars:.1f} ⭐\n\n"
                             "✅ Нажмите «Оплатить», чтобы продолжить:",
        'parsing_start': "🔍 *Запуск парсинга*\n\nВведите поисковый запрос:",
        'parsing_limit': "📊 Введите количество товаров (от 1 до 50):",
        'parsing_in_progress': "🔄 Парсинг запущен...\nЭто может занять до 30 секунд.",
        'parsing_complete': "✅ *Парсинг завершён!*\n\n📁 Результаты ниже:",
        'parsing_error': "❌ Ошибка при парсинге. Попробуйте позже.",
        'free_for_admin': "👑 Вы администратор — бесплатно!",
        'payment_required': "💳 *Оплата заказа*\n\nСумма: {price:.2f} ₽\n\nОтправьте на кошелёк:\n`{wallet}`\n\nПосле оплаты нажмите «Проверить оплату»",
        'payment_not_needed': "✅ Бесплатный доступ!\nВведите поисковый запрос:",
        'invalid_number': "❌ Введите число от 1 до 10000.",
        'invalid_limit': "❌ Введите число от 1 до 50.",
        'settings': "⚙️ Настройки",
        'support': "🆘 Поддержка",
        'parsing': "🕸️ Парсинг",
        'settings_text': "Настройки бота:",
        'change_lang': "🌐 Язык",
        'back': "◀️ Назад",
        'menu': "🏠 Меню",
        'pay': "💳 Оплатить",
        'check_payment': "✅ Проверить оплату",
        'create_ticket': "📝 Создать тикет",
        'enter_title': "Введите название проблемы:",
        'enter_description': "Введите описание:",
        'ticket_sent': "✅ Тикет отправлен!",
        'cancel': "❌ Отмена",
        'ticket_created_notify': "📩 Новый тикет от {name}\nТема: {title}\nОписание: {desc}",
        'ticket_closed': "✅ Тикет закрыт.",
        'no_active_tickets': "Нет активных тикетов.",
        'unknown_command': "❌ Неизвестная команда.",
        'checking_payment': "🔍 Проверяем оплату...\nПосле оплаты нажмите снова.",
    },
    'en': {
        'welcome': "🇬🇧 Welcome to ParsTape!",
        'lang_selected': "Language: English 🇬🇧",
        'main_menu_text': "📊 *ParsTape — Marketplace Parser*\n\nReal-time data from WB & Ozon.",
        'parsing_info': "🕸️ *Parsing WB & Ozon*\n\n💰 Price: 1 request = 1.2 ₽\n⭐ 1 star = 1.2 ₽\n\nEnter requests count:",
        'enter_requests': "🔢 Enter requests count:",
        'price_calculation': "📊 *Your order:*\n• Requests: {requests}\n• Price: {price:.2f} ₽\n• Stars: {stars:.1f} ⭐\n\nClick 'Pay':",
        'parsing_start': "🔍 Enter search query:",
        'parsing_limit': "📊 Enter items count (1-50):",
        'parsing_in_progress': "🔄 Parsing...",
        'parsing_complete': "✅ Done!\n📁 Results below:",
        'parsing_error': "❌ Error. Try again.",
        'free_for_admin': "👑 Admin access - free!",
        'payment_required': "💳 Pay {price:.2f} ₽ to:\n`{wallet}`\n\nClick 'Check payment' after sending:",
        'payment_not_needed': "✅ Free! Enter search query:",
        'invalid_number': "❌ Enter 1-10000.",
        'invalid_limit': "❌ Enter 1-50.",
        'settings': "⚙️ Settings",
        'support': "🆘 Support",
        'parsing': "🕸️ Parsing",
        'settings_text': "Settings:",
        'change_lang': "🌐 Language",
        'back': "◀️ Back",
        'menu': "🏠 Menu",
        'pay': "💳 Pay",
        'check_payment': "✅ Check payment",
        'create_ticket': "📝 Create ticket",
        'enter_title': "Enter title:",
        'enter_description': "Enter description:",
        'ticket_sent': "✅ Ticket sent!",
        'cancel': "❌ Cancel",
        'ticket_created_notify': "📩 New ticket from {name}\nTitle: {title}\nDesc: {desc}",
        'ticket_closed': "✅ Ticket closed.",
        'no_active_tickets': "No active tickets.",
        'unknown_command': "❌ Unknown command.",
        'checking_payment': "🔍 Checking payment...\nClick again after paying.",
    }
}

user_lang: Dict[int, str] = {}
active_tickets: Dict[int, dict] = {}
user_orders: Dict[int, dict] = {}
parsed_files: Dict[int, dict] = {}

# ==================== ПАРСЕР (через requests + BeautifulSoup) ====================
class ParsTape:
    def __init__(self):
        self.wb_products = []
        self.ozon_products = []
    
    async def fetch_html(self, url):
        """Асинхронная загрузка HTML"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                return await response.text()
    
    async def search_wildberries(self, query, limit):
        """Поиск на Wildberries через API"""
        products = []
        try:
            # Используем поисковый API Wildberries
            search_url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?appType=1&curr=rub&dest=-1257786&query={query}&resultset=catalog&sort=popular&spp=30&limit={limit}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers={'User-Agent': 'Mozilla/5.0'}) as response:
                    data = await response.json()
                    
                    if 'data' in data and 'products' in data['data']:
                        for product in data['data']['products'][:limit]:
                            name = product.get('name', '')
                            price = product.get('priceU', 0) / 100 if product.get('priceU') else 0
                            link = f"https://www.wildberries.ru/catalog/{product.get('id')}/detail.aspx"
                            
                            if name and price > 0:
                                products.append({
                                    'name': name[:100],
                                    'price': int(price),
                                    'link': link
                                })
                        
                        print(f"      ✅ WB: найдено {len(products)} товаров")
                    
        except Exception as e:
            print(f"      ❌ Ошибка WB: {e}")
        
        return products
    
    async def search_ozon(self, query, limit):
        """Поиск на Ozon через HTML"""
        products = []
        try:
            search_url = f"https://www.ozon.ru/search/?text={query}"
            
            html = await self.fetch_html(search_url)
            soup = BeautifulSoup(html, 'html.parser')
            
            # Поиск карточек товаров
            cards = soup.find_all('a', class_=re.compile(r'card'))
            if not cards:
                cards = soup.find_all('div', class_=re.compile(r'tile'))
            
            for card in cards[:limit]:
                try:
                    # Название
                    name_elem = card.find('span', class_=re.compile(r'tsBodyM'))
                    name = name_elem.get_text(strip=True) if name_elem else ''
                    
                    # Цена
                    price_elem = card.find('span', class_=re.compile(r'price'))
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        prices = re.findall(r'(\d[\d\s]*)', price_text)
                        if prices:
                            price = int(re.sub(r'\s', '', prices[0]))
                        else:
                            price = 0
                    else:
                        price = 0
                    
                    # Ссылка
                    link_elem = card.get('href')
                    if link_elem:
                        link = f"https://www.ozon.ru{link_elem}" if link_elem.startswith('/') else link_elem
                    else:
                        link = ''
                    
                    if name and price > 100:
                        products.append({
                            'name': name[:100],
                            'price': price,
                            'link': link
                        })
                except:
                    continue
            
            print(f"      ✅ Ozon: найдено {len(products)} товаров")
            
        except Exception as e:
            print(f"      ❌ Ошибка Ozon: {e}")
        
        return products
    
    async def search_both(self, query, limit, user_id=None):
        """Поиск на обеих площадках"""
        print(f"\n  🔍 ПОИСК: {query}")
        
        wb_products = await self.search_wildberries(query, limit)
        await asyncio.sleep(1)
        ozon_products = await self.search_ozon(query, limit)
        
        # Сохраняем файлы
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = re.sub(r'[^\w\s-]', '', query).replace(' ', '_')
        files = {}
        
        # Сводный файл
        summary_file = f"ParsTape_Summary_{safe_query}_{timestamp}.csv"
        with open(summary_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=['query', 'wb_count', 'ozon_count', 'total', 'timestamp'])
            writer.writeheader()
            writer.writerow({
                'query': query,
                'wb_count': len(wb_products),
                'ozon_count': len(ozon_products),
                'total': len(wb_products) + len(ozon_products),
                'timestamp': timestamp
            })
        files['summary'] = summary_file
        
        # Файл Wildberries
        if wb_products:
            wb_file = f"ParsTape_WB_{safe_query}_{timestamp}.csv"
            with open(wb_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['number', 'name', 'price', 'link'])
                writer.writeheader()
                for i, product in enumerate(wb_products, 1):
                    writer.writerow({
                        'number': i,
                        'name': product['name'],
                        'price': product['price'],
                        'link': product['link']
                    })
            files['wb'] = wb_file
        
        # Файл Ozon
        if ozon_products:
            ozon_file = f"ParsTape_Ozon_{safe_query}_{timestamp}.csv"
            with open(ozon_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['number', 'name', 'price', 'link'])
                writer.writeheader()
                for i, product in enumerate(ozon_products, 1):
                    writer.writerow({
                        'number': i,
                        'name': product['name'],
                        'price': product['price'],
                        'link': product['link']
                    })
            files['ozon'] = ozon_file
        
        return files, wb_products, ozon_products

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard(lang):
    kb = [
        [types.KeyboardButton(text=translations[lang]['settings'])],
        [types.KeyboardButton(text=translations[lang]['support'])],
        [types.KeyboardButton(text=translations[lang]['parsing'])]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard(lang):
    kb = [[types.KeyboardButton(text=translations[lang]['back'])]]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_menu_keyboard(lang):
    kb = [[types.KeyboardButton(text=translations[lang]['menu'])]]
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
    
def get_payment_keyboard(lang):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['pay'], callback_data="pay_order")],
        [InlineKeyboardButton(text=translations[lang]['back'], callback_data="back_to_main")]
    ])
    return kb

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

# ==================== ФУНКЦИИ ====================
def calculate_price(requests_count: int) -> tuple:
    """Расчёт цены: 1 запрос = 1.2 ₽"""
    price = requests_count * REQUEST_COEFFICIENT
    stars = requests_count * REQUEST_COEFFICIENT
    return price, stars

# ==================== ХЭНДЛЕРЫ ====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🌍 Выберите язык:", reply_markup=get_lang_keyboard())

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language(callback: CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_lang[callback.from_user.id] = lang_code
    await callback.message.delete()
    await callback.message.answer(
        translations[lang_code]['main_menu_text'],
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(lang_code)
    )
    await callback.answer()

@dp.message(F.text.in_({'🏠 Меню', '🏠 Menu'}))
async def menu_button(message: Message, state: FSMContext):
    await state.clear()
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(
        translations[lang]['main_menu_text'],
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(lang)
    )

@dp.message(F.text.in_({'◀️ Назад', '◀️ Back'}))
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(event, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    lang = user_lang.get(user_id, 'ru')
    if isinstance(event, CallbackQuery):
        await event.message.delete()
        await event.message.answer(
            translations[lang]['main_menu_text'],
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(lang)
        )
        await event.answer()
    else:
        await event.answer(
            translations[lang]['main_menu_text'],
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(lang)
        )

@dp.message(F.text.in_({'🕸️ Парсинг', '🕸️ Parsing'}))
async def parsing_menu(message: Message, state: FSMContext):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(
        translations[lang]['parsing_info'],
        parse_mode="Markdown",
        reply_markup=get_back_keyboard(lang)
    )
    await message.answer(translations[lang]['enter_requests'])
    await state.set_state(ParsingStates.waiting_for_requests)

@dp.message(ParsingStates.waiting_for_requests)
async def get_requests_count(message: Message, state: FSMContext):
    lang = user_lang.get(message.from_user.id, 'ru')
    try:
        requests_count = int(message.text)
        if requests_count < 1 or requests_count > 10000:
            await message.answer(translations[lang]['invalid_number'])
            return
        
        await state.update_data(requests=requests_count)
        price, stars = calculate_price(requests_count)
        
        await state.update_data(price=price, stars=stars)
        
        result_text = translations[lang]['price_calculation'].format(
            requests=requests_count,
            price=price,
            stars=stars
        )
        
        await message.answer(
            result_text,
            parse_mode="Markdown",
            reply_markup=get_payment_keyboard(lang)
        )
        
    except ValueError:
        await message.answer(translations[lang]['invalid_number'])

@dp.callback_query(lambda c: c.data == "pay_order")
async def process_payment(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    data = await state.get_data()
    
    # Проверяем, админ ли пользователь
    if user_id in ADMIN_IDS:
        # Админ - бесплатно
        await callback.message.edit_text(translations[lang]['payment_not_needed'])
        await callback.message.answer(translations[lang]['parsing_start'])
        await state.set_state(ParsingStates.waiting_for_query)
        await state.update_data(paid=True)
    else:
        # Обычный пользователь - запрос оплаты
        price = data.get('price', 0)
        
        payment_text = translations[lang]['payment_required'].format(
            price=price,
            wallet=CRYPTO_WALLET
        )
        
        # Сохраняем заказ
        user_orders[user_id] = {
            'requests': data.get('requests', 0),
            'price': price,
            'stars': data.get('stars', 0),
            'status': 'awaiting_payment'
        }
        
        # Создаём клавиатуру с проверкой оплаты
        check_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=translations[lang]['check_payment'], callback_data="check_payment")],
            [InlineKeyboardButton(text=translations[lang]['back'], callback_data="back_to_main")]
        ])
        
        await callback.message.edit_text(
            payment_text,
            parse_mode="Markdown",
            reply_markup=check_kb
        )
    
    await callback.answer()

@dp.callback_query(lambda c: c.data == "check_payment")
async def check_payment(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    
    await callback.message.answer(translations[lang]['checking_payment'])
    
    # Здесь можно добавить логику проверки оплаты через API криптовалюты
    # Пока просто симуляция - пользователь сам подтверждает
    
    # Запрашиваем подтверждение оплаты
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="payment_confirmed")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
    ])
    
    await callback.message.answer(
        "💰 Если вы отправили оплату, нажмите «Я оплатил».\n"
        "Мы проверим и запустим парсинг.",
        reply_markup=confirm_kb
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "payment_confirmed")
async def payment_confirmed(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    
    # Помечаем как оплачено
    if user_id in user_orders:
        user_orders[user_id]['status'] = 'paid'
    
    await callback.message.edit_text(translations[lang]['payment_not_needed'])
    await callback.message.answer(translations[lang]['parsing_start'])
    await state.set_state(ParsingStates.waiting_for_query)
    await state.update_data(paid=True)
    await callback.answer()

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
        
        # Запускаем парсинг
        parser = ParsTape()
        
        try:
            files, wb_products, ozon_products = await parser.search_both(query, limit, user_id)
            
            # Сохраняем файлы
            parsed_files[user_id] = files
            
            await wait_msg.delete()
            await message.answer(translations[lang]['parsing_complete'])
            
            # Отправляем файлы
            if 'wb' in files:
                await message.answer_document(
                    FSInputFile(files['wb']),
                    caption=f"📊 Wildberries: {len(wb_products)} товаров"
                )
            else:
                await message.answer("❌ На Wildberries ничего не найдено")
            
            if 'ozon' in files:
                await message.answer_document(
                    FSInputFile(files['ozon']),
                    caption=f"📊 Ozon: {len(ozon_products)} товаров"
                )
            else:
                await message.answer("❌ На Ozon ничего не найдено")
            
            if 'summary' in files:
                await message.answer_document(
                    FSInputFile(files['summary']),
                    caption="📈 Сводная статистика"
                )
            
            await message.answer(
                translations[lang]['main_menu_text'],
                parse_mode="Markdown",
                reply_markup=get_main_keyboard(lang)
            )
            await state.clear()
            
        except Exception as e:
            logging.error(f"Parsing error: {e}")
            await message.answer(translations[lang]['parsing_error'])
            
    except ValueError:
        await message.answer(translations[lang]['invalid_limit'])

@dp.message(F.text.in_({'⚙️ Настройки', '⚙️ Settings'}))
async def settings_menu(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(
        translations[lang]['settings_text'],
        reply_markup=get_settings_keyboard(lang)
    )

@dp.callback_query(lambda c: c.data == "change_lang")
async def change_lang(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌍 Выберите язык:",
        reply_markup=get_lang_keyboard()
    )
    await callback.answer()

@dp.message(F.text.in_({'🆘 Поддержка', '🆘 Support'}))
async def support_menu(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer("🛟", reply_markup=get_support_keyboard(lang))

@dp.callback_query(lambda c: c.data == "create_ticket")
async def create_ticket_start(callback: CallbackQuery, state: FSMContext):
    lang = user_lang.get(callback.from_user.id, 'ru')
    await callback.message.answer(
        translations[lang]['enter_title'],
        reply_markup=get_cancel_keyboard(lang)
    )
    await state.set_state(TicketStates.waiting_for_title)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_ticket")
async def cancel_ticket(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = user_lang.get(callback.from_user.id, 'ru')
    await callback.message.delete()
    await callback.message.answer(
        translations[lang]['main_menu_text'],
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(lang)
    )
    await callback.answer()

@dp.message(TicketStates.waiting_for_title)
async def get_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(
        translations[lang]['enter_description'],
        reply_markup=get_cancel_keyboard(lang)
    )
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
            await bot.send_message(
                admin_id,
                translations[lang]['ticket_created_notify'].format(name=name, title=title, desc=desc) +
                f"\n\n💬 /reply {user_id} [текст]\n🔒 /close_ticket_admin {user_id}"
            )
        except:
            pass

    await message.answer(
        translations[lang]['ticket_sent'],
        reply_markup=get_main_keyboard(lang)
    )
    await state.clear()

@dp.message(Command("reply"))
async def admin_reply(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("ℹ️ /reply USER_ID ТЕКСТ")
        return
    try:
        user_id = int(parts[1])
        reply_text = parts[2]
        lang = user_lang.get(user_id, 'ru')
        await bot.send_message(
            user_id,
            f"✉️ *Ответ поддержки:*\n{reply_text}\n\n/close_ticket",
            parse_mode="Markdown"
        )
        await message.answer(f"✅ Ответ отправлен")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

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
        await message.answer("Использование: /close_ticket_admin USER_ID")
        return
    try:
        user_id = int(parts[1])
        if user_id in active_tickets:
            del active_tickets[user_id]
            await message.answer(f"✅ Тикет {user_id} закрыт")
            lang = user_lang.get(user_id, 'ru')
            await bot.send_message(user_id, "🔒 Тикет закрыт администратором")
        else:
            await message.answer("Тикет не найден")
    except:
        await message.answer("Ошибка")

@dp.message(Command("admin"))
async def admin_check(message: Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    if user_id in ADMIN_IDS:
        await message.answer(
            f"✅ *Администратор*\n\n"
            f"📊 Статистика:\n"
            f"• Тикетов: {len(active_tickets)}\n"
            f"• Заказов: {len(user_orders)}\n"
            f"• Парсингов: {len(parsed_files)}",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"❌ Вы не админ. Ваш ID: {user_id}")

@dp.message()
async def unknown_command(message: Message, state: FSMContext):
    current_state = await state.get_state()
    lang = user_lang.get(message.from_user.id, 'ru')
    
    if not current_state:
        await message.answer(
            translations[lang]['unknown_command'],
            reply_markup=get_main_keyboard(lang)
        )

async def main():
    print("🚀 Бот ParsTape запущен!")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"💰 Курс: 1 запрос = {REQUEST_COEFFICIENT} ₽")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
