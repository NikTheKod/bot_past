import asyncio
import logging
import os
import csv
import re
import aiohttp
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
PRICE_PER_REQUEST = 1.2  # 1 запрос = 1.2 ₽

logging.basicConfig(level=logging.INFO)

# --- СОСТОЯНИЯ ---
class Form(StatesGroup):
    waiting_requests = State()   # ждём количество товаров/запросов
    waiting_payment = State()    # ждём подтверждения оплаты
    waiting_query = State()      # ждём поисковый запрос

class TicketStates(StatesGroup):
    waiting_title = State()
    waiting_desc = State()

# --- ПЕРЕВОДЫ ---
t = {
    'ru': {
        'start': "🇷🇺 Добро пожаловать в ParsTape!",
        'main': "📊 *ParsTape — парсинг маркетплейсов*\n\nWildberries и Ozon\nАвтоматический сбор данных",
        'requests_info': "💰 1 товар = 1.2 ₽\n\nВведите количество товаров для сбора (1-500):",
        'price_msg': "📊 *Ваш заказ:* {req} товаров = {price:.2f} ₽\n\nНажмите «Оплатить»",
        'free_admin': "👑 Админ — бесплатно!\n\nВведите поисковый запрос:",
        'need_pay': "💳 *Оплатите {price:.2f} ₽*\n\nКошелёк: `{wallet}`\n\nПосле оплаты нажмите «Я оплатил»",
        'wait_pay': "⏳ Ожидаем подтверждения оплаты от администратора...",
        'pay_ok': "✅ Оплата подтверждена!\n\nВведите поисковый запрос:",
        'pay_no': "❌ Оплата не подтверждена. Обратитесь в поддержку /support",
        'ask_query': "🔍 Введите поисковый запрос (например: iphone, наушники, телевизор):",
        'parsing_start': "🔄 Начинаем парсинг...\nЭто займёт 10-30 секунд",
        'parsing_done': "✅ *Парсинг завершён!*",
        'no_results': "❌ По запросу «{query}» ничего не найдено.\nПопробуйте другой запрос.",
        'wb_found': "📦 *Wildberries:* {count} товаров",
        'ozon_found': "📦 *Ozon:* {count} товаров",
        'invalid_num': "❌ Введите число от 1 до 500",
        'settings': "⚙️ Настройки",
        'support': "🆘 Поддержка",
        'parsing_btn': "🕸️ Парсинг",
        'back': "◀️ Назад",
        'menu': "🏠 Меню",
        'pay_btn': "💳 Оплатить",
        'i_paid_btn': "✅ Я оплатил",
        'change_lang': "🌐 Язык",
        'create_ticket': "📝 Создать тикет",
        'ticket_title': "Введите тему обращения:",
        'ticket_desc': "Опишите вашу проблему:",
        'ticket_sent': "✅ Тикет отправлен администраторам!",
        'ticket_new': "📩 *НОВЫЙ ТИКЕТ*\n\n👤 От: {name}\n🆔 ID: {user}\n📝 Тема: {title}\n📄 Описание: {desc}\n\n💬 /reply {user} [текст ответа]\n🔒 /close_ticket {user}",
        'reply_format': "📝 Использование: /reply USER_ID ТЕКСТ",
        'reply_sent': "✅ Ответ отправлен пользователю",
        'reply_msg': "✉️ *Ответ поддержки:*\n{text}\n\n🔒 Если вопрос решён, нажмите /close_ticket",
        'ticket_closed': "✅ Тикет закрыт. Спасибо за обращение!",
        'no_ticket': "❌ У вас нет активных тикетов",
        'ticket_closed_admin': "✅ Тикет пользователя {user} закрыт",
        'unknown': "❌ Неизвестная команда. Используйте кнопки меню.",
        'admin_stats': "✅ *Администратор*\n\n📊 Тикетов: {tickets}\n⏳ Ожидают оплату: {payments}",
        'confirm_payment': "💰 *ПОДТВЕРЖДЕНИЕ ОПЛАТЫ*\n\n👤 Пользователь: {name}\n🆔 ID: {user}\n📊 Товаров: {req}\n💰 Сумма: {price:.2f} ₽\n\n✅ /confirm_{user} - подтвердить\n❌ /reject_{user} - отклонить",
        'confirm_ok': "✅ Оплата пользователя {user} подтверждена",
        'reject_ok': "❌ Оплата пользователя {user} отклонена",
    },
    'en': {
        'start': "🇬🇧 Welcome to ParsTape!",
        'main': "📊 *ParsTape — Marketplace Parser*\n\nWildberries & Ozon",
        'requests_info': "💰 1 item = 1.2 ₽\n\nEnter number of items to collect (1-500):",
        'price_msg': "📊 *Your order:* {req} items = {price:.2f} ₽\n\nClick 'Pay'",
        'free_admin': "👑 Admin — free!\n\nEnter search query:",
        'need_pay': "💳 *Pay {price:.2f} ₽*\n\nWallet: `{wallet}`\n\nClick 'I paid' after sending",
        'wait_pay': "⏳ Waiting for admin confirmation...",
        'pay_ok': "✅ Payment confirmed!\n\nEnter search query:",
        'pay_no': "❌ Payment not confirmed. Contact support /support",
        'ask_query': "🔍 Enter search query (e.g., iphone, headphones):",
        'parsing_start': "🔄 Starting parsing...\nThis will take 10-30 seconds",
        'parsing_done': "✅ *Parsing completed!*",
        'no_results': "❌ No results for '{query}'.\nTry another query.",
        'wb_found': "📦 *Wildberries:* {count} items",
        'ozon_found': "📦 *Ozon:* {count} items",
        'invalid_num': "❌ Enter a number between 1 and 500",
        'settings': "⚙️ Settings",
        'support': "🆘 Support",
        'parsing_btn': "🕸️ Parsing",
        'back': "◀️ Back",
        'menu': "🏠 Menu",
        'pay_btn': "💳 Pay",
        'i_paid_btn': "✅ I paid",
        'change_lang': "🌐 Language",
        'create_ticket': "📝 Create ticket",
        'ticket_title': "Enter ticket title:",
        'ticket_desc': "Describe your problem:",
        'ticket_sent': "✅ Ticket sent to admins!",
        'ticket_new': "📩 *NEW TICKET*\n\n👤 From: {name}\n🆔 ID: {user}\n📝 Title: {title}\n📄 Description: {desc}\n\n💬 /reply {user} [reply text]\n🔒 /close_ticket {user}",
        'reply_format': "📝 Usage: /reply USER_ID TEXT",
        'reply_sent': "✅ Reply sent to user",
        'reply_msg': "✉️ *Support reply:*\n{text}\n\n🔒 If solved, click /close_ticket",
        'ticket_closed': "✅ Ticket closed. Thank you!",
        'no_ticket': "❌ You have no active tickets",
        'ticket_closed_admin': "✅ Ticket for user {user} closed",
        'unknown': "❌ Unknown command. Use menu buttons.",
        'admin_stats': "✅ *Admin*\n\n📊 Tickets: {tickets}\n⏳ Pending payments: {payments}",
        'confirm_payment': "💰 *PAYMENT CONFIRMATION*\n\n👤 User: {name}\n🆔 ID: {user}\n📊 Items: {req}\n💰 Amount: {price:.2f} ₽\n\n✅ /confirm_{user} - confirm\n❌ /reject_{user} - reject",
        'confirm_ok': "✅ Payment for user {user} confirmed",
        'reject_ok': "❌ Payment for user {user} rejected",
    }
}

user_lang: Dict[int, str] = {}
user_orders: Dict[int, dict] = {}  # {user_id: {'requests': 10, 'price': 12}}
pending_payments: Dict[int, dict] = {}  # {user_id: {'requests': 10, 'price': 12, 'name': '...'}}
active_tickets: Dict[int, dict] = {}

# ==================== ПАРСЕР ====================
async def parse_wildberries(query: str, limit: int):
    products = []
    try:
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
    except Exception as e:
        print(f"WB error: {e}")
    return products

async def parse_ozon(query: str, limit: int):
    products = []
    try:
        url = f"https://www.ozon.ru/search/?text={query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # Ищем JSON данные в HTML
                    json_match = re.search(r'window\.__STATE__\s*=\s*({.*?});', html)
                    if json_match:
                        data = json.loads(json_match.group(1))
                        # Парсим JSON Ozon (сложно, но рабочий вариант через поиск ссылок)
                    # Упрощённый парсинг через поиск ссылок
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'lxml')
                    for card in soup.find_all('a', href=re.compile(r'/product/'))[:limit*2]:
                        try:
                            name_elem = card.find('span', class_=re.compile(r'tsBodyM|tile-title'))
                            name = name_elem.get_text(strip=True) if name_elem else ''
                            if not name:
                                continue
                            price_elem = card.find('span', class_=re.compile(r'price|final'))
                            price = 0
                            if price_elem:
                                price_text = price_elem.get_text(strip=True)
                                nums = re.findall(r'(\d[\d\s]*)', price_text)
                                if nums:
                                    price = int(re.sub(r'\s', '', nums[0]))
                            if price > 0 and len(products) < limit:
                                href = card.get('href', '')
                                link = f"https://www.ozon.ru{href}" if href.startswith('/') else href
                                products.append({'name': name[:80], 'price': price, 'link': link})
                        except:
                            continue
    except Exception as e:
        print(f"Ozon error: {e}")
    return products

async def parse_both(query: str, limit: int):
    print(f"🔍 Парсинг: {query}, лимит: {limit}")
    wb = await parse_wildberries(query, limit)
    print(f"WB: {len(wb)} товаров")
    await asyncio.sleep(1)
    ozon = await parse_ozon(query, limit)
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

@dp.message(F.text.in_({'🏠 Меню', '🏠 Menu'}))
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
    await message.answer(t[lang]['requests_info'], reply_markup=get_back_keyboard(lang))

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
        
        # Сохраняем заказ
        user_orders[message.from_user.id] = {'requests': count, 'price': price}
        
        # Админ или нет?
        if message.from_user.id in ADMIN_IDS:
            await state.set_state(Form.waiting_query)
            await message.answer(t[lang]['free_admin'])
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
    
    # Сохраняем в ожидание оплаты
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

@dp.message(lambda m: m.text and m.text.startswith('/confirm_'))
async def confirm_payment(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    
    user_id = int(message.text.replace('/confirm_', '').strip())
    lang = user_lang.get(user_id, 'ru')
    
    if user_id in pending_payments:
        del pending_payments[user_id]
        
        # Уведомляем пользователя
        await bot.send_message(user_id, t[lang]['pay_ok'])
        await bot.send_message(user_id, t[lang]['ask_query'])
        
        # Устанавливаем состояние через отдельное сообщение
        await dp.fsm.storage.set_state(key=(user_id, user_id), state=Form.waiting_query)
        
        await message.answer(t[lang]['confirm_ok'].format(user=user_id))
    else:
        await message.answer(f"❌ Платёж для {user_id} не найден")

@dp.message(lambda m: m.text and m.text.startswith('/reject_'))
async def reject_payment(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет прав")
        return
    
    user_id = int(message.text.replace('/reject_', '').strip())
    lang = user_lang.get(user_id, 'ru')
    
    if user_id in pending_payments:
        del pending_payments[user_id]
        await bot.send_message(user_id, t[lang]['pay_no'])
        await message.answer(t[lang]['reject_ok'].format(user=user_id))
    else:
        await message.answer(f"❌ Платёж для {user_id} не найден")

@dp.message(Form.waiting_query)
async def get_search_query(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    query = message.text.strip()
    
    await state.update_data(query=query)
    
    # Получаем количество товаров из заказа
    order = user_orders.get(user_id, {})
    limit = order.get('requests', 10)
    
    wait_msg = await message.answer(t[lang]['parsing_start'])
    
    try:
        files, wb_products, ozon_products = await parse_both(query, limit)
        await wait_msg.delete()
        
        if not wb_products and not ozon_products:
            await message.answer(t[lang]['no_results'].format(query=query))
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
            
            await message.answer_document(FSInputFile(files['summary']), caption="📈 Сводная статистика")
        
        await message.answer(t[lang]['main'], parse_mode="Markdown", reply_markup=get_main_keyboard(lang))
        await state.clear()
        
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
    await message.answer(t[lang]['settings'], reply_markup=kb)

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
    await callback.message.answer(t[lang]['ticket_title'], reply_markup=get_cancel_keyboard(lang))
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
    await message.answer(t[lang]['ticket_desc'], reply_markup=get_cancel_keyboard(lang))
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
    
    await message.answer(t[lang]['ticket_sent'], reply_markup=get_main_keyboard(lang))
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
        await message.answer(t[lang]['ticket_closed'])
    else:
        await message.answer(t[lang]['no_ticket'])

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
            await bot.send_message(user_id, "🔒 Ваш тикет закрыт администратором")
        else:
            await message.answer("Тикет не найден")
    except:
        await message.answer("Ошибка")

@dp.message(Command("admin"))
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
        await message.answer(t[lang]['unknown'], reply_markup=get_main_keyboard(lang))

async def main():
    print("🚀 Бот запущен!")
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"💰 Цена: {PRICE_PER_REQUEST} ₽ за товар")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
