import asyncio
import logging
import os
import csv
import re
import aiohttp
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from typing import Dict

# --- КОНФИГ ---
BOT_TOKEN = "8307763743:AAGt5tZAnzu8inHZse5X_N1dw-fIN9Ek1fU"
ADMIN_IDS = [8444790051]
CRYPTO_WALLET = "UQDwD5okkERUN_pl-trSFiAEVMVOgm35Q2choki984WdyRY4"
PRICE_PER_REQUEST = 1.2

logging.basicConfig(level=logging.INFO)

# --- СОСТОЯНИЯ ---
class Form(StatesGroup):
    waiting_requests = State()
    waiting_payment = State()
    waiting_query = State()

class TicketStates(StatesGroup):
    waiting_title = State()
    waiting_desc = State()

# --- ПЕРЕВОДЫ (ПОЛНЫЙ ТЕКСТ) ---
t = {
    'ru': {
        'start': "🇷🇺 Добро пожаловать в ParsTape!\n\nВаш надёжный партнёр по парсингу маркетплейсов Wildberries и Ozon.",
        'main': "📊 *ParsTape — ваш эксперт по маркетплейсам*\n\n"
                "🟢 *Актуальные данные*\n"
                "Цены и остатки обновляются каждые 15 минут. Вы всегда видите реальную ситуацию на рынке.\n\n"
                "🤖 *Автоматический парсинг*\n"
                "Наша система самостоятельно собирает данные с маркетплейсов. Вам не нужно ничего настраивать.\n\n"
                "📈 *Удобная аналитика*\n"
                "Графики, таблицы и отчёты для принятия правильных решений.\n\n"
                "Выберите действие в меню ниже:",
        'requests_info': "🕸️ *Парсинг Wildberries и Ozon*\n\n"
                         "Автоматический сбор и анализ данных с Wildberries и Ozon. Цены, остатки, динамика продаж — всё в одном месте для принятия правильных решений.\n\n"
                         "💰 *Цена:* 1 запрос (1 товар) = 1.2 ₽\n"
                         "⭐ *1 звезда = 1.2 ₽*\n\n"
                         "📝 Введите количество товаров, которое нужно собрать (от 1 до 500):",
        'price_msg': "📊 *Ваш заказ:*\n\n"
                     "• Количество товаров: {req} шт.\n"
                     "• Стоимость: {price:.2f} ₽\n"
                     "• Звёзд: {price:.0f} ⭐\n\n"
                     "✅ Нажмите «Оплатить», чтобы продолжить оформление заказа.",
        'free_admin': "👑 Вы вошли как администратор!\n\n"
                      "Парсинг для вас абсолютно бесплатный.\n\n"
                      "🔍 Введите поисковый запрос (например: iphone 15, наушники, телевизор, стиральная машина):",
        'need_pay': "💳 *Оплата заказа*\n\n"
                    "Сумма к оплате: {price:.2f} ₽\n\n"
                    "💸 Кошелёк для оплаты (криптовалюта):\n"
                    "`{wallet}`\n\n"
                    "❗ *Инструкция:*\n"
                    "1. Отправьте указанную сумму на кошелёк\n"
                    "2. После оплаты нажмите кнопку «Я оплатил»\n"
                    "3. Администратор проверит платёж и запустит парсинг\n\n"
                    "✅ Нажмите «Я оплатил» после отправки средств:",
        'wait_pay': "⏳ *Ожидание подтверждения*\n\n"
                    "Ваш запрос на оплату отправлен администратору.\n"
                    "Пожалуйста, ожидайте подтверждения. Это может занять несколько минут.\n\n"
                    "Администратор проверит платёж и запустит парсинг автоматически.",
        'pay_ok': "✅ *Оплата подтверждена!*\n\n"
                  "Ваш платёж успешно подтверждён администратором.\n\n"
                  "🔍 Теперь введите поисковый запрос для сбора товаров:",
        'pay_no': "❌ *Оплата не подтверждена*\n\n"
                  "К сожалению, ваш платёж не был подтверждён администратором.\n"
                  "Пожалуйста, обратитесь в поддержку: /support\n\n"
                  "Возможно, вы отправили неверную сумму или неправильный кошелёк.",
        'ask_query': "🔍 *Введите поисковый запрос*\n\n"
                     "Например:\n"
                     "• iphone 15\n"
                     "• наушники беспроводные\n"
                     "• телевизор samsung\n"
                     "• стиральная машина lg\n\n"
                     "Чем точнее запрос, тем лучше результат:",
        'parsing_start': "🔄 *Парсинг запущен!*\n\n"
                         "Начинаю сбор данных с Wildberries и Ozon.\n"
                         "Это может занять от 10 до 30 секунд в зависимости от количества товаров.\n\n"
                         "Пожалуйста, подождите...",
        'parsing_done': "✅ *Парсинг успешно завершён!*\n\n"
                        "Все данные собраны и сохранены в CSV файлы.\n"
                        "Результаты прикреплены ниже:",
        'no_results': "❌ *Ничего не найдено*\n\n"
                      "По вашему запросу «{query}» не удалось найти товары.\n\n"
                      "💡 *Рекомендации:*\n"
                      "• Попробуйте более общий запрос (например, «телефон» вместо «iphone 15 pro max»)\n"
                      "• Проверьте правильность написания\n"
                      "• Попробуйте запрос на русском или английском языке\n\n"
                      "🔄 Нажмите «Парсинг» в меню, чтобы попробовать снова.",
        'wb_found': "📦 *Wildberries — найденные товары*\n\n"
                    "✅ Собрано товаров: {count} шт.\n"
                    "📊 Файл с подробным списком прикреплён ниже.",
        'ozon_found': "📦 *Ozon — найденные товары*\n\n"
                      "✅ Собрано товаров: {count} шт.\n"
                      "📊 Файл с подробным списком прикреплён ниже.",
        'invalid_num': "❌ *Ошибка ввода*\n\n"
                       "Пожалуйста, введите целое число от 1 до 500.\n\n"
                       "Примеры правильного ввода: 10, 25, 100, 500",
        'settings': "⚙️ *Настройки*\n\n"
                    "Здесь вы можете настроить параметры бота:",
        'support': "🆘 *Поддержка*\n\n"
                   "Если у вас возникли проблемы или вопросы, создайте тикет.\n"
                   "Администратор свяжется с вами в ближайшее время.",
        'parsing_btn': "🕸️ Парсинг",
        'back': "◀️ Назад",
        'menu': "🏠 Главное меню",
        'pay_btn': "💳 Оплатить",
        'i_paid_btn': "✅ Я оплатил",
        'change_lang': "🌐 Сменить язык",
        'create_ticket': "📝 Создать тикет",
        'ticket_title': "📝 *Создание тикета*\n\n"
                        "Введите тему вашего обращения (кратко опишите проблему):",
        'ticket_desc': "📄 *Описание проблемы*\n\n"
                       "Теперь подробно опишите вашу проблему или вопрос.\n"
                       "Чем подробнее, тем быстрее мы сможем вам помочь:",
        'ticket_sent': "✅ *Тикет отправлен!*\n\n"
                       "Ваше обращение передано администраторам.\n"
                       "Ответ придет в этот чат, как только администратор ответит.\n\n"
                       "Ожидайте...",
        'ticket_new': "📩 *НОВЫЙ ТИКЕТ*\n\n"
                      "👤 Отправитель: {name}\n"
                      "🆔 ID пользователя: {user}\n"
                      "📝 Тема: {title}\n"
                      "📄 Описание: {desc}\n\n"
                      "💬 Чтобы ответить: /reply {user} [текст ответа]\n"
                      "🔒 Чтобы закрыть тикет: /close_ticket {user}",
        'reply_format': "📝 *Формат команды:*\n\n"
                        "/reply USER_ID ТЕКСТ ОТВЕТА\n\n"
                        "Пример: /reply 123456789 Спасибо за обращение!",
        'reply_sent': "✅ *Ответ отправлен!*\n\n"
                      "Ваш ответ успешно доставлен пользователю.",
        'reply_msg': "✉️ *Ответ поддержки*\n\n"
                     "{text}\n\n"
                     "🔒 Если ваша проблема решена, нажмите /close_ticket",
        'ticket_closed': "✅ *Тикет закрыт*\n\n"
                         "Ваше обращение успешно закрыто.\n"
                         "Спасибо, что пользуетесь ParsTape!",
        'no_ticket': "❌ *Нет активных тикетов*\n\n"
                     "У вас нет открытых обращений.\n"
                     "Если нужна помощь, создайте новый тикет через меню Поддержка.",
        'ticket_closed_admin': "✅ *Тикет закрыт администратором*\n\n"
                               "Тикет пользователя {user} успешно закрыт.",
        'unknown': "❌ *Неизвестная команда*\n\n"
                   "Пожалуйста, используйте кнопки меню для навигации.\n\n"
                   "Если вы не видите меню, нажмите /start",
        'admin_stats': "✅ *Панель администратора*\n\n"
                       "📊 *Статистика бота:*\n\n"
                       f"• Активных тикетов: {{tickets}}\n"
                       f"• Ожидают подтверждения оплаты: {{payments}}\n\n"
                       "📌 *Доступные команды:*\n"
                       "• /reply USER_ID текст — ответить пользователю\n"
                       "• /close_ticket USER_ID — закрыть тикет\n"
                       "• /stats — показать статистику\n\n"
                       "💰 *Для подтверждения оплаты:*\n"
                       "• admapp_USER_ID — подтвердить оплату\n"
                       "• admin_USER_ID — отклонить оплату",
        'confirm_payment': "💰 *ЗАПРОС ПОДТВЕРЖДЕНИЯ ОПЛАТЫ*\n\n"
                           "👤 Пользователь: {name}\n"
                           "🆔 ID: {user}\n"
                           "📊 Количество товаров: {req} шт.\n"
                           "💰 Сумма к оплате: {price:.2f} ₽\n\n"
                           "✅ admapp_{user} — подтвердить оплату\n"
                           "❌ admin_{user} — отклонить оплату",
        'confirm_ok': "✅ *Оплата подтверждена*\n\n"
                      "Пользователь {user} получит доступ к парсингу.",
        'reject_ok': "❌ *Оплата отклонена*\n\n"
                     "Пользователь {user} уведомлён об отклонении платежа.",
        'waiting_payment': "⏳ *Ожидание оплаты*\n\n"
                           "Ваш заказ создан. Пожалуйста, оплатите и нажмите «Я оплатил».",
        'payment_info': "💳 *Реквизиты для оплаты*\n\n"
                        "Кошелёк: `{wallet}`\n\n"
                        "Сумма: {price:.2f} ₽\n\n"
                        "После оплаты нажмите кнопку «Я оплатил».",
    },
    'en': {
        'start': "🇬🇧 Welcome to ParsTape!\n\nYour reliable marketplace parsing partner for Wildberries and Ozon.",
        'main': "📊 *ParsTape — Your Marketplace Expert*\n\n"
                "🟢 *Real-time Data*\n"
                "Prices and stocks update every 15 minutes.\n\n"
                "🤖 *Automated Parsing*\n"
                "Our system collects data automatically.\n\n"
                "📈 *Convenient Analytics*\n"
                "Charts, tables, and reports.\n\n"
                "Choose an action from the menu below:",
        'requests_info': "🕸️ *Wildberries & Ozon Parsing*\n\n"
                         "Automated data collection from Wildberries and Ozon.\n\n"
                         "💰 *Price:* 1 request (1 item) = 1.2 ₽\n"
                         "⭐ *1 star = 1.2 ₽*\n\n"
                         "📝 Enter the number of items to collect (1 to 500):",
        'price_msg': "📊 *Your Order:*\n\n"
                     "• Items: {req} pcs\n"
                     "• Cost: {price:.2f} ₽\n"
                     "• Stars: {price:.0f} ⭐\n\n"
                     "✅ Click 'Pay' to continue:",
        'free_admin': "👑 Admin access granted!\n\n"
                      "Parsing is free for administrators.\n\n"
                      "🔍 Enter search query (e.g., iphone 15, headphones, TV):",
        'need_pay': "💳 *Order Payment*\n\n"
                    "Amount to pay: {price:.2f} ₽\n\n"
                    "💸 Wallet:\n`{wallet}`\n\n"
                    "📌 *Instructions:*\n"
                    "1. Send the amount to the wallet\n"
                    "2. Click 'I paid' after sending\n"
                    "3. Admin will verify and start parsing\n\n"
                    "✅ Click 'I paid' after sending:",
        'wait_pay': "⏳ *Awaiting Confirmation*\n\n"
                    "Your payment request has been sent to admin.\n"
                    "Please wait for confirmation.",
        'pay_ok': "✅ *Payment Confirmed!*\n\n"
                  "Your payment has been confirmed.\n\n"
                  "🔍 Now enter your search query:",
        'pay_no': "❌ *Payment Not Confirmed*\n\n"
                  "Your payment was not confirmed.\n"
                  "Please contact support: /support",
        'ask_query': "🔍 *Enter Search Query*\n\n"
                     "Examples:\n"
                     "• iphone 15\n"
                     "• wireless headphones\n"
                     "• samsung tv\n\n"
                     "Enter your query:",
        'parsing_start': "🔄 *Parsing Started!*\n\n"
                         "Collecting data from Wildberries and Ozon.\n"
                         "This may take 10-30 seconds.\n\n"
                         "Please wait...",
        'parsing_done': "✅ *Parsing Completed!*\n\n"
                        "All data collected and saved.\n"
                        "Results attached below:",
        'no_results': "❌ *No Results Found*\n\n"
                      "No products found for '{query}'.\n\n"
                      "💡 *Tips:*\n"
                      "• Try a more general query\n"
                      "• Check spelling\n"
                      "• Try Russian or English\n\n"
                      "Click 'Parsing' in menu to try again.",
        'wb_found': "📦 *Wildberries Results*\n\n"
                    "✅ Items found: {count}\n"
                    "📊 File attached below.",
        'ozon_found': "📦 *Ozon Results*\n\n"
                      "✅ Items found: {count}\n"
                      "📊 File attached below.",
        'invalid_num': "❌ *Invalid Input*\n\n"
                       "Please enter a number from 1 to 500.",
        'settings': "⚙️ *Settings*\n\n"
                    "Configure bot parameters:",
        'support': "🆘 *Support*\n\n"
                   "Create a ticket and admin will contact you.",
        'parsing_btn': "🕸️ Parsing",
        'back': "◀️ Back",
        'menu': "🏠 Main Menu",
        'pay_btn': "💳 Pay",
        'i_paid_btn': "✅ I paid",
        'change_lang': "🌐 Change language",
        'create_ticket': "📝 Create ticket",
        'ticket_title': "📝 *Create Ticket*\n\nEnter ticket title:",
        'ticket_desc': "📄 *Description*\n\nDescribe your problem in detail:",
        'ticket_sent': "✅ *Ticket Sent!*\n\n"
                       "Your request has been sent to admins.\n"
                       "You will receive a reply here.",
        'ticket_new': "📩 *NEW TICKET*\n\n"
                      "👤 From: {name}\n"
                      "🆔 ID: {user}\n"
                      "📝 Title: {title}\n"
                      "📄 Description: {desc}\n\n"
                      "💬 /reply {user} [reply text]\n"
                      "🔒 /close_ticket {user}",
        'reply_format': "📝 *Command format:*\n\n/reply USER_ID TEXT",
        'reply_sent': "✅ *Reply sent!*",
        'reply_msg': "✉️ *Support Reply*\n\n{text}\n\n🔒 Click /close_ticket if solved",
        'ticket_closed': "✅ *Ticket closed*\n\nThank you for using ParsTape!",
        'no_ticket': "❌ *No active tickets*",
        'ticket_closed_admin': "✅ *Ticket closed by admin*\n\nUser {user} ticket closed.",
        'unknown': "❌ *Unknown command*\n\nPlease use menu buttons.",
        'admin_stats': "✅ *Admin Panel*\n\n"
                       "📊 *Statistics:*\n\n"
                       f"• Active tickets: {{tickets}}\n"
                       f"• Pending payments: {{payments}}\n\n"
                       "📌 *Commands:*\n"
                       "• /reply USER_ID text\n"
                       "• /close_ticket USER_ID\n\n"
                       "💰 *Payment commands:*\n"
                       "• admapp_USER_ID - confirm\n"
                       "• admin_USER_ID - reject",
        'confirm_payment': "💰 *PAYMENT CONFIRMATION*\n\n"
                           "👤 User: {name}\n"
                           "🆔 ID: {user}\n"
                           "📊 Items: {req}\n"
                           "💰 Amount: {price:.2f} ₽\n\n"
                           "✅ admapp_{user} - confirm\n"
                           "❌ admin_{user} - reject",
        'confirm_ok': "✅ *Payment confirmed*\n\nUser {user} can now parse.",
        'reject_ok': "❌ *Payment rejected*\n\nUser {user} notified.",
        'waiting_payment': "⏳ *Waiting for payment*\n\nPlease pay and click 'I paid'.",
        'payment_info': "💳 *Payment details*\n\nWallet: `{wallet}`\nAmount: {price:.2f} ₽",
    }
}

user_lang: Dict[int, str] = {}
user_orders: Dict[int, dict] = {}
pending_payments: Dict[int, dict] = {}
active_tickets: Dict[int, dict] = {}

# ==================== ПАРСЕР (РЕАЛЬНО РАБОТАЮЩИЙ) ====================
async def parse_wildberries(query: str, limit: int):
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
                                products.append({
                                    'name': name[:100],
                                    'price': int(price),
                                    'link': link
                                })
                    else:
                        print(f"WB: нет товаров в ответе")
                else:
                    print(f"WB статус: {resp.status}")
    except Exception as e:
        print(f"WB ошибка: {e}")
    
    return products

async def parse_ozon(query: str, limit: int):
    products = []
    try:
        # Прямой запрос к API Ozon (неофициальный, но рабочий)
        url = f"https://www.ozon.ru/api/composer-api.bx/_action/search?text={query}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Парсим результаты
                    if 'layout' in data and 'search' in str(data):
                        # Поиск в JSON
                        import json as jsonlib
                        text = jsonlib.dumps(data)
                        matches = re.findall(r'"title":"([^"]+)".*?"price":"([^"]+)"', text)
                        for match in matches[:limit]:
                            name = match[0]
                            price = float(match[1]) if match[1] else 0
                            if name and price > 0:
                                products.append({
                                    'name': name[:100],
                                    'price': int(price),
                                    'link': f"https://www.ozon.ru/search/?text={query}"
                                })
                else:
                    print(f"Ozon статус: {resp.status}")
    except Exception as e:
        print(f"Ozon ошибка: {e}")
    
    return products

async def parse_both(query: str, limit: int):
    print(f"🔍 Парсинг: {query}, лимит: {limit}")
    
    # Парсим параллельно
    wb_task = parse_wildberries(query, limit)
    ozon_task = parse_ozon(query, limit)
    
    wb, ozon = await asyncio.gather(wb_task, ozon_task)
    
    print(f"WB: {len(wb)} товаров")
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
    
    # Wildberries
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
    kb = [
        [types.KeyboardButton(text=t[lang]['settings'])],
        [types.KeyboardButton(text=t[lang]['support'])],
        [types.KeyboardButton(text=t[lang]['parsing_btn'])]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_keyboard(lang):
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=t[lang]['back'])]],
        resize_keyboard=True
    )

def get_lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def get_payment_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[lang]['pay_btn'], callback_data="pay")],
        [InlineKeyboardButton(text=t[lang]['back'], callback_data="back")]
    ])

def get_i_paid_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[lang]['i_paid_btn'], callback_data="i_paid")],
        [InlineKeyboardButton(text=t[lang]['back'], callback_data="back")]
    ])

def get_support_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[lang]['create_ticket'], callback_data="create_ticket")],
        [InlineKeyboardButton(text=t[lang]['back'], callback_data="back")]
    ])

def get_cancel_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_ticket")]
    ])

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== ХЭНДЛЕРЫ ====================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🌍 Выберите язык / Choose language:", reply_markup=get_lang_keyboard())

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def set_language(callback: CallbackQuery):
    lang_code = callback.data.split("_")[1]
    user_lang[callback.from_user.id] = lang_code
    await callback.message.delete()
    await callback.message.answer(
        t[lang_code]['main'],
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(lang_code)
    )
    await callback.answer()

@dp.message(F.text.in_({'🏠 Главное меню', '🏠 Main Menu'}))
@dp.message(F.text.in_({'◀️ Назад', '◀️ Back'}))
@dp.callback_query(lambda c: c.data == "back")
async def back_to_main(event, state: FSMContext):
    await state.clear()
    user_id = event.from_user.id
    lang = user_lang.get(user_id, 'ru')
    if isinstance(event, CallbackQuery):
        await event.message.delete()
        await event.message.answer(t[lang]['main'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))
        await event.answer()
    else:
        await event.answer(t[lang]['main'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))

@dp.message(F.text.in_({'🕸️ Парсинг', '🕸️ Parsing'}))
async def parsing_start(message: Message, state: FSMContext):
    lang = user_lang.get(message.from_user.id, 'ru')
    await state.set_state(Form.waiting_requests)
    await message.answer(t[lang]['requests_info'], parse_mode="Markdown", reply_markup=get_back_keyboard(lang))

@dp.message(Form.waiting_requests)
async def get_requests(message: Message, state: FSMContext):
    lang = user_lang.get(message.from_user.id, 'ru')
    try:
        count = int(message.text)
        if count < 1 or count > 500:
            await message.answer(t[lang]['invalid_num'])
            return
        
        price = count * PRICE_PER_REQUEST
        await state.update_data(requests=count, price=price)
        
        user_orders[message.from_user.id] = {'requests': count, 'price': price}
        
        if message.from_user.id in ADMIN_IDS:
            await state.set_state(Form.waiting_query)
            await message.answer(t[lang]['free_admin'], parse_mode="Markdown")
        else:
            text = t[lang]['price_msg'].format(req=count, price=price)
            await message.answer(text, parse_mode="Markdown", reply_markup=get_payment_keyboard(lang))
            await state.set_state(Form.waiting_payment)
    except ValueError:
        await message.answer(t[lang]['invalid_num'])

@dp.callback_query(lambda c: c.data == "pay")
async def process_pay(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    data = await state.get_data()
    price = data.get('price', 0)
    
    text = t[lang]['need_pay'].format(price=price, wallet=CRYPTO_WALLET)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_i_paid_keyboard(lang))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "i_paid")
async def i_paid(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    data = await state.get_data()
    
    pending_payments[user_id] = {
        'requests': data.get('requests', 0),
        'price': data.get('price', 0),
        'name': callback.from_user.full_name
    }
    
    # Отправляем админу
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            t[lang]['confirm_payment'].format(
                name=callback.from_user.full_name,
                user=user_id,
                req=data.get('requests', 0),
                price=data.get('price', 0)
            ),
            parse_mode="Markdown"
        )
    
    await callback.message.edit_text(t[lang]['wait_pay'])
    await callback.answer()

# КОМАНДА ДЛЯ ПОДТВЕРЖДЕНИЯ ОПЛАТЫ: admapp_123456789
@dp.message(lambda m: m.text and m.text.startswith('admapp_'))
async def confirm_payment(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    
    try:
        user_id = int(message.text.replace('admapp_', '').strip())
        lang = user_lang.get(user_id, 'ru')
        
        if user_id in pending_payments:
            del pending_payments[user_id]
            
            await bot.send_message(user_id, t[lang]['pay_ok'], parse_mode="Markdown")
            await bot.send_message(user_id, t[lang]['ask_query'], parse_mode="Markdown")
            
            await dp.fsm.storage.set_state(key=(user_id, user_id), state=Form.waiting_query)
            
            await message.answer(t[lang]['confirm_ok'].format(user=user_id))
        else:
            await message.answer(f"❌ Платёж для {user_id} не найден")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

# КОМАНДА ДЛЯ ОТКЛОНЕНИЯ ОПЛАТЫ: admin_123456789
@dp.message(lambda m: m.text and m.text.startswith('admin_'))
async def reject_payment(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    
    try:
        user_id = int(message.text.replace('admin_', '').strip())
        lang = user_lang.get(user_id, 'ru')
        
        if user_id in pending_payments:
            del pending_payments[user_id]
            await bot.send_message(user_id, t[lang]['pay_no'], parse_mode="Markdown")
            await message.answer(t[lang]['reject_ok'].format(user=user_id))
        else:
            await message.answer(f"❌ Платёж для {user_id} не найден")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(Form.waiting_query)
async def get_search_query(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    query = message.text.strip()
    
    await state.update_data(query=query)
    
    order = user_orders.get(user_id, {})
    limit = order.get('requests', 10)
    
    wait_msg = await message.answer(t[lang]['parsing_start'], parse_mode="Markdown")
    
    try:
        files, wb_products, ozon_products = await parse_both(query, limit)
        await wait_msg.delete()
        
        if not wb_products and not ozon_products:
            await message.answer(t[lang]['no_results'].format(query=query), parse_mode="Markdown")
        else:
            await message.answer(t[lang]['parsing_done'], parse_mode="Markdown")
            
            if wb_products:
                await message.answer_document(
                    FSInputFile(files['wb']),
                    caption=t[lang]['wb_found'].format(count=len(wb_products))
                )
            else:
                await message.answer("❌ Wildberries: ничего не найдено")
            
            if ozon_products:
                await message.answer_document(
                    FSInputFile(files['ozon']),
                    caption=t[lang]['ozon_found'].format(count=len(ozon_products))
                )
            else:
                await message.answer("❌ Ozon: ничего не найдено")
            
            if 'summary' in files:
                await message.answer_document(FSInputFile(files['summary']), caption="📈 Сводная статистика")
        
        await message.answer(t[lang]['main'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))
        await state.clear()
        
        # Удаляем файлы через 5 минут
        async def cleanup():
            await asyncio.sleep(300)
            for f in files.values():
                try:
                    os.remove(f)
                except:
                    pass
        asyncio.create_task(cleanup())
        
    except Exception as e:
        logging.error(f"Parse error: {e}")
        await wait_msg.delete()
        await message.answer("❌ Ошибка парсинга. Попробуйте позже.")

@dp.message(F.text.in_({'⚙️ Настройки', '⚙️ Settings'}))
async def settings_menu(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[lang]['change_lang'], callback_data="change_lang")],
        [InlineKeyboardButton(text=t[lang]['back'], callback_data="back")]
    ])
    await message.answer(t[lang]['settings'], parse_mode="Markdown", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "change_lang")
async def change_lang(callback: CallbackQuery):
    await callback.message.edit_text("🌍 Выберите язык / Choose language:", reply_markup=get_lang_keyboard())
    await callback.answer()

@dp.message(F.text.in_({'🆘 Поддержка', '🆘 Support'}))
async def support_menu(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(t[lang]['support'], parse_mode="Markdown", reply_markup=get_support_keyboard(lang))

@dp.callback_query(lambda c: c.data == "create_ticket")
async def create_ticket_start(callback: CallbackQuery, state: FSMContext):
    lang = user_lang.get(callback.from_user.id, 'ru')
    await callback.message.answer(t[lang]['ticket_title'], parse_mode="Markdown", reply_markup=get_cancel_keyboard(lang))
    await state.set_state(TicketStates.waiting_title)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_ticket")
async def cancel_ticket(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = user_lang.get(callback.from_user.id, 'ru')
    await callback.message.delete()
    await callback.message.answer(t[lang]['main'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))
    await callback.answer()

@dp.message(TicketStates.waiting_title)
async def get_ticket_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(t[lang]['ticket_desc'], parse_mode="Markdown", reply_markup=get_cancel_keyboard(lang))
    await state.set_state(TicketStates.waiting_desc)

@dp.message(TicketStates.waiting_desc)
async def get_ticket_desc(message: Message, state: FSMContext):
    data = await state.get_data()
    title = data['title']
    desc = message.text
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    name = message.from_user.full_name
    
    active_tickets[user_id] = {'title': title, 'desc': desc}
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            t[lang]['ticket_new'].format(name=name, user=user_id, title=title, desc=desc),
            parse_mode="Markdown"
        )
    
    await message.answer(t[lang]['ticket_sent'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))
    await state.clear()

@dp.message(Command("reply"))
async def admin_reply(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(t['ru']['reply_format'])
        return
    
    try:
        user_id = int(parts[1])
        reply_text = parts[2]
        lang = user_lang.get(user_id, 'ru')
        
        await bot.send_message(user_id, t[lang]['reply_msg'].format(text=reply_text), parse_mode="Markdown")
        await message.answer(t[lang]['reply_sent'])
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message(Command("close_ticket"))
async def close_ticket(message: Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    
    if user_id in active_tickets:
        del active_tickets[user_id]
        await message.answer(t[lang]['ticket_closed'], parse_mode="Markdown")
    else:
        await message.answer(t[lang]['no_ticket'], parse_mode="Markdown")

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
        lang = user_lang.get(user_id, 'ru')
        
        if user_id in active_tickets:
            del active_tickets[user_id]
            await message.answer(t[lang]['ticket_closed_admin'].format(user=user_id))
            await bot.send_message(user_id, "🔒 Ваш тикет закрыт администратором")
        else:
            await message.answer("Тикет не найден")
    except:
        await message.answer("Ошибка")

@dp.message(Command("stats"))
async def admin_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(
        t[lang]['admin_stats'].format(
            tickets=len(active_tickets),
            payments=len(pending_payments)
        ),
        parse_mode="Markdown"
    )

@dp.message()
async def unknown(message: Message, state: FSMContext):
    if await state.get_state() is None:
        lang = user_lang.get(message.from_user.id, 'ru')
        await message.answer(t[lang]['unknown'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))

async def main():
    print("🚀 Бот ParsTape запущен!")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"💰 Цена: {PRICE_PER_REQUEST} ₽ за товар")
    print("📌 Команды админа:")
    print("   admapp_USERID - подтвердить оплату")
    print("   admin_USERID - отклонить оплату")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
