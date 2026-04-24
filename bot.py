import asyncio
import logging
import os
import time
import random
import csv
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from typing import Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- КОНФИГ ---
BOT_TOKEN = "8307763743:AAGt5tZAnzu8inHZse5X_N1dw-fIN9Ek1fU"
ADMIN_IDS = [8444790051]
CRYPTO_WALLET = "UQDwD5okkERUN_pl-trSFiAEVMVOgm35Q2choki984WdyRY4"  # Ваш кошелёк

logging.basicConfig(level=logging.INFO)

# --- СОСТОЯНИЯ ---
class TicketStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()

class ParsingStates(StatesGroup):
    waiting_for_requests = State()
    waiting_for_query = State()  # Ожидание поискового запроса
    waiting_for_limit = State()   # Ожидание количества товаров

# --- ПЕРЕВОДЫ ---
translations = {
    'ru': {
        'welcome': "🇷🇺 Добро пожаловать в ParsTape!\nВаш надёжный парсинг маркетплейсов на заказ.",
        'lang_selected': "Язык установлен: русский 🇷🇺",
        'main_menu': "📋 Главное меню:",
        'main_menu_text': "📊 *ParsTape — ваш эксперт по маркетплейсам*\n\n"
                          "🟢 *Актуальные данные*\n"
                          "Цены и остатки обновляются каждые 15 минут. Вы всегда видите реальную ситуацию на рынке.\n\n"
                          "🤖 *Автоматический парсинг*\n"
                          "Наша система самостоятельно собирает данные с маркетплейсов. Вам не нужно ничего настраивать.\n\n"
                          "📈 *Удобная аналитика*\n"
                          "Графики, таблицы и отчёты для принятия правильных решений.",
        'parsing_info': "🕸️ *Парсинг Wildberries и Ozon*\n\n"
                        "Автоматический сбор и анализ данных с Wildberries и Ozon. Цены, остатки, динамика продаж — всё в одном месте для принятия правильных решений.\n\n"
                        "💰 *Тарифы:*\n"
                        "• 100 запросов — 1290 ₽\n"
                        "• 10 000 запросов — 5000 ₽\n\n"
                        "⭐ *1 звезда = 1 запрос*\n\n"
                        "📝 Введите количество запросов (от 1 до 10000), и я рассчитаю стоимость в звёздах:",
        'enter_requests': "🔢 Введите количество запросов (от 1 до 10000):",
        'price_calculation': "📊 *Ваш заказ:*\n"
                             "• Запросов: {requests} шт.\n"
                             "• Стоимость: {price} ₽\n"
                             "• Звёзд: {stars} ⭐\n\n"
                             "✅ Нажмите «Оплатить», чтобы продолжить:",
        'parsing_start': "🔍 *Запуск парсинга*\n\n"
                         "Введите поисковый запрос (например: *айфон 15*, *наушники*, *телевизор*):",
        'parsing_limit': "📊 Введите количество товаров для сбора (от 1 до 100):",
        'parsing_in_progress': "🔄 Парсинг запущен...\n"
                               "Это может занять несколько минут.\n"
                               "Пожалуйста, подождите...",
        'parsing_complete': "✅ *Парсинг завершён!*\n\n"
                            "📁 Файлы готовы к скачиванию:\n"
                            "• Сводная статистика\n"
                            "• Wildberries (все товары)\n"
                            "• Ozon (все товары)\n\n"
                            "📥 Нажмите кнопку ниже, чтобы скачать архив с результатами:",
        'parsing_error': "❌ Произошла ошибка при парсинге.\n"
                         "Пожалуйста, попробуйте позже или обратитесь в поддержку.",
        'free_for_admin': "👑 Вы администратор — парсинг бесплатно!",
        'payment_required': "💳 *Оплата заказа*\n\n"
                            "Сумма к оплате: {price} ₽\n\n"
                            "Отправьте оплату на кошелёк:\n"
                            "`{wallet}`\n\n"
                            "После оплаты пришлите чек и название товара.\n"
                            "Ваш заказ будет выполнен после подтверждения.",
        'payment_not_needed': "✅ Как администратор, вы получаете парсинг бесплатно!\n"
                              "Запускаем парсинг...",
        'invalid_number': "❌ Пожалуйста, введите число от 1 до 10000.",
        'invalid_limit': "❌ Пожалуйста, введите число от 1 до 100.",
        'settings': "⚙️ Настройки",
        'support': "🆘 Поддержка",
        'parsing': "🕸️ Парсинг",
        'settings_text': "Здесь вы можете изменить язык или просмотреть данные.",
        'change_lang': "🌐 Изменить язык",
        'back': "◀️ Назад",
        'menu': "🏠 Меню",
        'pay': "💳 Оплатить",
        'create_ticket': "📝 Создать тикет",
        'enter_title': "Введите название вашего вопроса/проблемы:",
        'enter_description': "Теперь введите подробное описание:",
        'ticket_sent': "✅ Ваш тикет отправлен админам. Ожидайте ответа.",
        'cancel': "❌ Отмена",
        'ticket_created_notify': "📩 Новый тикет от {name}\nНазвание: {title}\nОписание: {desc}",
        'ticket_closed': "✅ Тикет закрыт. Спасибо!",
        'no_active_tickets': "Нет активных тикетов.",
        'unknown_command': "❌ Неизвестная команда. Пожалуйста, используйте кнопки меню.",
        'download': "📥 Скачать CSV файлы",
        'no_files': "Нет файлов для скачивания. Запустите парсинг сначала.",
    },
    'en': {
        'welcome': "🇬🇧 Welcome to ParsTape!\nYour custom marketplace parsing service.",
        'lang_selected': "Language set: English 🇬🇧",
        'main_menu': "📋 Main menu:",
        'main_menu_text': "📊 *ParsTape — your marketplace expert*\n\n"
                          "🟢 *Real-time data*\n"
                          "Prices and stocks update every 15 minutes. You always see the real market situation.\n\n"
                          "🤖 *Automated parsing*\n"
                          "Our system collects data from marketplaces automatically. No setup needed.\n\n"
                          "📈 *Convenient analytics*\n"
                          "Charts, tables and reports for making the right decisions.",
        'parsing_info': "🕸️ *Wildberries & Ozon Parsing*\n\n"
                        "Automated collection and analysis of data from Wildberries and Ozon. Prices, stocks, sales dynamics — all in one place for making the right decisions.\n\n"
                        "💰 *Pricing:*\n"
                        "• 100 requests — 1290 ₽\n"
                        "• 10,000 requests — 5000 ₽\n\n"
                        "⭐ *1 star = 1 request*\n\n"
                        "📝 Enter the number of requests (1 to 10000) to calculate the cost in stars:",
        'enter_requests': "🔢 Enter the number of requests (1 to 10000):",
        'price_calculation': "📊 *Your order:*\n"
                             "• Requests: {requests} pcs\n"
                             "• Cost: {price} ₽\n"
                             "• Stars: {stars} ⭐\n\n"
                             "✅ Click 'Pay' to continue:",
        'parsing_start': "🔍 *Start parsing*\n\n"
                         "Enter search query (e.g., *iphone 15*, *headphones*, *tv*):",
        'parsing_limit': "📊 Enter number of items to collect (1 to 100):",
        'parsing_in_progress': "🔄 Parsing started...\n"
                               "This may take a few minutes.\n"
                               "Please wait...",
        'parsing_complete': "✅ *Parsing completed!*\n\n"
                            "📁 Files ready for download:\n"
                            "• Summary statistics\n"
                            "• Wildberries (all items)\n"
                            "• Ozon (all items)\n\n"
                            "📥 Click the button below to download the results:",
        'parsing_error': "❌ An error occurred during parsing.\n"
                         "Please try again later or contact support.",
        'free_for_admin': "👑 You are admin — parsing is free!",
        'payment_required': "💳 *Payment for order*\n\n"
                            "Amount to pay: {price} ₽\n\n"
                            "Send payment to wallet:\n"
                            "`{wallet}`\n\n"
                            "After payment, send the receipt and product name.\n"
                            "Your order will be processed after confirmation.",
        'payment_not_needed': "✅ As an admin, you get parsing for free!\n"
                              "Starting parsing...",
        'invalid_number': "❌ Please enter a number between 1 and 10000.",
        'invalid_limit': "❌ Please enter a number between 1 and 100.",
        'settings': "⚙️ Settings",
        'support': "🆘 Support",
        'parsing': "🕸️ Parsing",
        'settings_text': "Here you can change language or view info.",
        'change_lang': "🌐 Change language",
        'back': "◀️ Back",
        'menu': "🏠 Menu",
        'pay': "💳 Pay",
        'create_ticket': "📝 Create ticket",
        'enter_title': "Enter the title of your issue:",
        'enter_description': "Now enter a detailed description:",
        'ticket_sent': "✅ Your ticket has been sent. Wait for a reply.",
        'cancel': "❌ Cancel",
        'ticket_created_notify': "📩 New ticket from {name}\nTitle: {title}\nDescription: {desc}",
        'ticket_closed': "✅ Ticket closed. Thank you!",
        'no_active_tickets': "No active tickets.",
        'unknown_command': "❌ Unknown command. Please use the menu buttons.",
        'download': "📥 Download CSV files",
        'no_files': "No files to download. Run parsing first.",
    }
}

user_lang: Dict[int, str] = {}
active_tickets: Dict[int, dict] = {}
user_orders: Dict[int, dict] = {}  # Храним заказы пользователей
parsed_files: Dict[int, dict] = {}  # Храним пути к созданным файлам

# ==================== ПАРСЕР (из вашего файла) ====================
class ParsTape:
    def __init__(self):
        self.wb_products_log = []
        self.ozon_products_log = []
        
    def create_driver(self):
        options = Options()
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless")  # Добавил headless режим для сервера
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    def random_delay(self, min_sec=0.5, max_sec=2):
        time.sleep(random.uniform(min_sec, max_sec))
    
    def search_wildberries(self, query, limit):
        driver = None
        try:
            driver = self.create_driver()
            search_url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={query}"
            print(f"      🌐 Открываю Wildberries...")
            
            driver.get(search_url)
            self.random_delay(4, 6)
            
            products = []
            seen_names = set()
            scroll_attempts = 0
            max_scrolls = 50
            
            while len(products) < limit and scroll_attempts < max_scrolls:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.random_delay(1.5, 2.5)
                
                cards = driver.find_elements(By.CSS_SELECTOR, ".product-card, .j-card-item, [class*='product-card']")
                
                for card in cards:
                    try:
                        name = ""
                        name_selectors = [".goods-name", ".product-name", ".brand-name", "[class*='name']"]
                        for selector in name_selectors:
                            try:
                                name_elem = card.find_element(By.CSS_SELECTOR, selector)
                                name = name_elem.text.strip()
                                if name:
                                    break
                            except:
                                continue
                        
                        price = 0
                        price_selectors = [".price__lower-price", ".price-block__final-price", "[class*='price']", "ins"]
                        for selector in price_selectors:
                            try:
                                price_elem = card.find_element(By.CSS_SELECTOR, selector)
                                price_text = price_elem.text.strip()
                                numbers = re.findall(r'(\d[\d\s]*)', price_text)
                                if numbers:
                                    price = int(re.sub(r'\s', '', numbers[0]))
                                    break
                            except:
                                continue
                        
                        link = ""
                        try:
                            link_elem = card.find_element(By.CSS_SELECTOR, "a")
                            href = link_elem.get_attribute("href")
                            if href:
                                link = href
                        except:
                            pass
                        
                        unique_key = f"{name}_{price}"
                        
                        if name and 100 < price < 1000000 and unique_key not in seen_names:
                            seen_names.add(unique_key)
                            products.append({
                                "name": name[:100],
                                "price": price,
                                "link": link
                            })
                            if len(products) >= limit:
                                break
                    except:
                        continue
                
                scroll_attempts += 1
                if len(products) >= limit:
                    break
            
            driver.quit()
            
            if products:
                self.wb_products_log.extend(products)
                return {
                    "min_price": min(p['price'] for p in products),
                    "max_price": max(p['price'] for p in products),
                    "count": len(products),
                    "products": products
                }
            return {"min_price": 0, "max_price": 0, "count": 0, "products": []}
            
        except Exception as e:
            print(f"      ❌ Ошибка WB: {str(e)[:50]}")
            if driver:
                driver.quit()
            return {"min_price": 0, "max_price": 0, "count": 0, "products": []}
    
    def search_ozon(self, query, limit):
        driver = None
        try:
            driver = self.create_driver()
            search_url = f"https://www.ozon.ru/search/?text={query}"
            print(f"      🌐 Открываю Ozon...")
            
            driver.get(search_url)
            self.random_delay(4, 6)
            
            products = []
            seen_names = set()
            scroll_attempts = 0
            max_scrolls = 50
            
            while len(products) < limit and scroll_attempts < max_scrolls:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.random_delay(1.5, 2.5)
                
                cards = driver.find_elements(By.CSS_SELECTOR, "[class*='tile'], a[class*='card']")
                
                for card in cards:
                    try:
                        card_text = card.text
                        lines = card_text.split('\n')
                        name = lines[0].strip() if lines else ""
                        
                        price = 0
                        price_match = re.search(r'(\d[\d\s]*)\s*₽', card_text)
                        if price_match:
                            price = int(re.sub(r'\s', '', price_match.group(1)))
                        
                        link = ""
                        try:
                            link_elem = card.find_element(By.CSS_SELECTOR, "a")
                            link = link_elem.get_attribute("href")
                        except:
                            pass
                        
                        unique_key = f"{name}_{price}"
                        
                        if name and 100 < price < 1000000 and unique_key not in seen_names and len(name) > 3:
                            seen_names.add(unique_key)
                            products.append({
                                "name": name[:100],
                                "price": price,
                                "link": link
                            })
                            if len(products) >= limit:
                                break
                    except:
                        continue
                
                scroll_attempts += 1
                if len(products) >= limit:
                    break
            
            driver.quit()
            
            if products:
                self.ozon_products_log.extend(products)
                return {
                    "min_price": min(p['price'] for p in products),
                    "max_price": max(p['price'] for p in products),
                    "count": len(products),
                    "products": products
                }
            return {"min_price": 0, "max_price": 0, "count": 0, "products": []}
            
        except Exception as e:
            print(f"      ❌ Ошибка Ozon: {str(e)[:50]}")
            if driver:
                driver.quit()
            return {"min_price": 0, "max_price": 0, "count": 0, "products": []}
    
    def search_both(self, query, limit, user_id=None):
        print(f"\n  🔍 ПОИСК: {query}")
        
        wb = self.search_wildberries(query, limit)
        self.random_delay(3, 5)
        oz = self.search_ozon(query, limit)
        
        # Сохраняем файлы
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = re.sub(r'[^\w\s-]', '', query).replace(' ', '_')
        files = {}
        
        # Сводный файл
        summary_file = f"ParsTape_Summary_{safe_query}_{timestamp}.csv"
        with open(summary_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'query', 'wb_count', 'wb_min_price', 'wb_max_price',
                'ozon_count', 'ozon_min_price', 'ozon_max_price',
                'total_products', 'cheapest_price'
            ])
            writer.writeheader()
            writer.writerow({
                'query': query,
                'wb_count': wb['count'],
                'wb_min_price': wb['min_price'],
                'ozon_count': oz['count'],
                'ozon_min_price': oz['min_price'],
                'ozon_max_price': oz['max_price'],
                'total_products': wb['count'] + oz['count'],
                'cheapest_price': min(wb['min_price'], oz['min_price']) if wb['min_price'] and oz['min_price'] else wb['min_price'] or oz['min_price']
            })
        files['summary'] = summary_file
        
        # Файл Wildberries
        if wb['count'] > 0:
            wb_file = f"ParsTape_Wildberries_{safe_query}_{timestamp}.csv"
            with open(wb_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['number', 'name', 'price', 'link'])
                writer.writeheader()
                for i, product in enumerate(wb['products'], 1):
                    writer.writerow({
                        'number': i,
                        'name': product['name'],
                        'price': product['price'],
                        'link': product.get('link', '')
                    })
            files['wb'] = wb_file
        
        # Файл Ozon
        if oz['count'] > 0:
            ozon_file = f"ParsTape_Ozon_{safe_query}_{timestamp}.csv"
            with open(ozon_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=['number', 'name', 'price', 'link'])
                writer.writeheader()
                for i, product in enumerate(oz['products'], 1):
                    writer.writerow({
                        'number': i,
                        'name': product['name'],
                        'price': product['price'],
                        'link': product.get('link', '')
                    })
            files['ozon'] = ozon_file
        
        return files

# ==================== КЛАВИАТУРЫ ====================
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

def get_payment_keyboard(lang):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['pay'], callback_data="pay_order")],
        [InlineKeyboardButton(text=translations[lang]['back'], callback_data="back_to_main")]
    ])
    return kb

def get_download_keyboard(lang):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=translations[lang]['download'], callback_data="download_files")],
        [InlineKeyboardButton(text=translations[lang]['menu'], callback_data="back_to_main")]
    ])
    return kb

# ==================== ФУНКЦИИ ====================
def calculate_price(requests_count: int) -> tuple:
    if requests_count <= 100:
        price = 1290
    else:
        price = int(requests_count * 0.5)
    return price, requests_count

# ==================== ХЭНДЛЕРЫ ====================
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
    await callback.message.answer(
        translations[lang_code]['main_menu_text'],
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(lang_code)
    )
    await callback.answer()

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

@dp.message(F.text.in_({'🏠 Меню', '🏠 Menu'}))
async def menu_button(message: Message, state: FSMContext):
    await state.clear()
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(
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
        
        result_text = translations[lang]['price_calculation'].format(
            requests=requests_count,
            price=price,
            stars=stars
        )
        
        await state.update_data(price=price, stars=stars)
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
    
    # Проверяем, админ ли пользователь
    if user_id in ADMIN_IDS:
        await callback.message.edit_text(translations[lang]['payment_not_needed'])
        # Запускаем парсинг
        await callback.message.answer(translations[lang]['parsing_start'])
        await state.set_state(ParsingStates.waiting_for_query)
        await state.update_data(requests=None, price=0)  # Админу бесплатно
    else:
        data = await state.get_data()
        price = data.get('price', 0)
        
        payment_text = translations[lang]['payment_required'].format(
            price=price,
            wallet=CRYPTO_WALLET
        )
        await callback.message.edit_text(
            payment_text,
            parse_mode="Markdown",
            reply_markup=get_back_keyboard(lang)
        )
        # Сохраняем заказ
        user_orders[user_id] = {
            'requests': data.get('requests', 0),
            'price': price,
            'status': 'awaiting_payment'
        }
    
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
        if limit < 1 or limit > 100:
            await message.answer(translations[lang]['invalid_limit'])
            return
        
        data = await state.get_data()
        query = data.get('query', '')
        
        await message.answer(translations[lang]['parsing_in_progress'])
        
        # Запускаем парсинг в отдельном потоке
        loop = asyncio.get_event_loop()
        parser = ParsTape()
        
        try:
            files = await loop.run_in_executor(None, parser.search_both, query, limit, user_id)
            
            # Сохраняем файлы для пользователя
            parsed_files[user_id] = files
            
            # Отправляем файлы
            await message.answer(translations[lang]['parsing_complete'])
            
            # Отправляем CSV файлы
            if 'wb' in files:
                await message.answer_document(
                    FSInputFile(files['wb']),
                    caption="📊 Wildberries — полный список товаров"
                )
            if 'ozon' in files:
                await message.answer_document(
                    FSInputFile(files['ozon']),
                    caption="📊 Ozon — полный список товаров"
                )
            if 'summary' in files:
                await message.answer_document(
                    FSInputFile(files['summary']),
                    caption="📈 Сводная статистика по парсингу"
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
        "🌍 Выберите язык / Choose language:",
        reply_markup=get_lang_keyboard()
    )
    await callback.answer()

@dp.message(F.text.in_({'🆘 Поддержка', '🆘 Support'}))
async def support_menu(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer("🛟 Выберите действие:", reply_markup=get_support_keyboard(lang))

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
                f"\n\n💬 Чтобы ответить: /reply {user_id} [текст]\n"
                f"Чтобы закрыть тикет: /close_ticket_admin {user_id}"
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
        await message.answer("ℹ️ Использование: /reply USER_ID ТЕКСТ ОТВЕТА")
        return
    try:
        user_id = int(parts[1])
        reply_text = parts[2]
        lang = user_lang.get(user_id, 'ru')
        await bot.send_message(
            user_id,
            f"✉️ *Ответ поддержки:*\n{reply_text}\n\n🔄 Если вопрос решён, нажмите /close_ticket",
            parse_mode="Markdown"
        )
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
        
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"📌 Пользователь {user_id} закрыл тикет")
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
            await message.answer(f"✅ Тикет пользователя {user_id} закрыт")
            lang = user_lang.get(user_id, 'ru')
            await bot.send_message(user_id, "🔒 Ваш тикет закрыт администратором. Спасибо за обращение!")
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
            f"✅ *Вы администратор!*\n\n"
            f"📊 Статистика:\n"
            f"• Активных тикетов: {len(active_tickets)}\n"
            f"• Ожидающих оплату: {len(user_orders)}\n"
            f"• Выполненных парсингов: {len(parsed_files)}\n\n"
            f"📌 Команды:\n"
            f"/reply USER_ID текст — ответить пользователю\n"
            f"/close_ticket_admin USER_ID — закрыть тикет\n"
            f"/stats — статистика бота",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"❌ Вы не администратор. Ваш ID: {user_id}")

@dp.message(Command("stats"))
async def show_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    await message.answer(
        f"📊 *Статистика бота*\n\n"
        f"👥 Пользователей: {len(user_lang)}\n"
        f"🎫 Активных тикетов: {len(active_tickets)}\n"
        f"💰 Ожидают оплату: {len(user_orders)}\n"
        f"✅ Выполнено парсингов: {len(parsed_files)}",
        parse_mode="Markdown"
    )

# Обработчик неизвестных команд
@dp.message()
async def unknown_command(message: Message, state: FSMContext):
    current_state = await state.get_state()
    lang = user_lang.get(message.from_user.id, 'ru')
    
    if current_state:
        await message.answer(translations[lang]['unknown_command'])
    else:
        await message.answer(
            translations[lang]['unknown_command'],
            reply_markup=get_main_keyboard(lang)
        )

async def main():
    print("🚀 Бот ParsTape запущен!")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"💳 Кошелёк: {CRYPTO_WALLET}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
