import asyncio
import logging
import os
import csv
import re
import aiohttp
import random
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

logging.basicConfig(level=logging.INFO)

# --- СОСТОЯНИЯ ---
class Form(StatesGroup):
    waiting_query = State()
    waiting_limit = State()

class TicketStates(StatesGroup):
    waiting_title = State()
    waiting_desc = State()

# --- ПЕРЕВОДЫ ---
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
        'parsing_info': "🕸️ *Парсинг Wildberries и Ozon*\n\n"
                        "Автоматический сбор и анализ данных с Wildberries и Ozon.\n\n"
                        "📝 Введите поисковый запрос (например: iphone, наушники, телевизор):",
        'parsing_limit': "📊 Введите количество товаров для сбора (от 1 до 50):",
        'parsing_start': "🔄 *Парсинг запущен!*\n\n"
                         "Начинаю сбор данных с Wildberries и Ozon.\n"
                         "Это может занять от 10 до 30 секунд.\n\n"
                         "Пожалуйста, подождите...",
        'parsing_done': "✅ *Парсинг успешно завершён!*\n\n"
                        "Все данные собраны и сохранены в CSV файлы.\n"
                        "Результаты прикреплены ниже:",
        'no_results': "❌ *Ничего не найдено*\n\n"
                      "По вашему запросу «{query}» не удалось найти товары.\n\n"
                      "💡 *Рекомендации:*\n"
                      "• Попробуйте более общий запрос\n"
                      "• Проверьте правильность написания\n\n"
                      "🔄 Нажмите «Парсинг» в меню, чтобы попробовать снова.",
        'wb_found': "📦 *Wildberries — найденные товары*\n\n"
                    "✅ Собрано товаров: {count} шт.\n"
                    "📊 Файл с подробным списком прикреплён ниже.",
        'ozon_found': "📦 *Ozon — найденные товары*\n\n"
                      "✅ Собрано товаров: {count} шт.\n"
                      "📊 Файл с подробным списком прикреплён ниже.",
        'invalid_limit': "❌ *Ошибка ввода*\n\n"
                         "Пожалуйста, введите целое число от 1 до 50.",
        'settings': "⚙️ *Настройки*\n\n"
                    "Здесь вы можете настроить параметры бота:",
        'support': "🆘 *Поддержка*\n\n"
                   "Если у вас возникли проблемы или вопросы, создайте тикет.\n"
                   "Администратор свяжется с вами в ближайшее время.",
        'parsing_btn': "🕸️ Парсинг",
        'back': "◀️ Назад",
        'menu': "🏠 Главное меню",
        'change_lang': "🌐 Сменить язык",
        'create_ticket': "📝 Создать тикет",
        'ticket_title': "📝 *Создание тикета*\n\n"
                        "Введите тему вашего обращения (кратко опишите проблему):",
        'ticket_desc': "📄 *Описание проблемы*\n\n"
                       "Теперь подробно опишите вашу проблему или вопрос:",
        'ticket_sent': "✅ *Тикет отправлен!*\n\n"
                       "Ваше обращение передано администраторам.\n"
                       "Ответ придет в этот чат, как только администратор ответит.",
        'ticket_new': "📩 *НОВЫЙ ТИКЕТ*\n\n"
                      "👤 Отправитель: {name}\n"
                      "🆔 ID пользователя: {user}\n"
                      "📝 Тема: {title}\n"
                      "📄 Описание: {desc}\n\n"
                      "💬 Чтобы ответить: /reply {user} [текст ответа]\n"
                      "🔒 Чтобы закрыть тикет: /close_ticket {user}",
        'reply_format': "📝 *Формат команды:*\n\n/reply USER_ID ТЕКСТ ОТВЕТА",
        'reply_sent': "✅ *Ответ отправлен!*",
        'reply_msg': "✉️ *Ответ поддержки*\n\n{text}\n\n🔒 Если проблема решена, нажмите /close_ticket",
        'ticket_closed': "✅ *Тикет закрыт*\n\nСпасибо за обращение!",
        'no_ticket': "❌ *Нет активных тикетов*",
        'ticket_closed_admin': "✅ *Тикет закрыт администратором*\n\nТикет пользователя {user} закрыт.",
        'unknown': "❌ *Неизвестная команда*\n\nИспользуйте кнопки меню.",
        'admin_stats': "✅ *Панель администратора*\n\n"
                       "📊 *Статистика бота:*\n\n"
                       f"• Активных тикетов: {{tickets}}\n\n"
                       "📌 *Доступные команды:*\n"
                       "• /reply USER_ID текст — ответить пользователю\n"
                       "• /close_ticket USER_ID — закрыть тикет\n"
                       "• /stats — показать статистику",
        'tech_work': "🔧 *Технические работы*\n\n"
                     "Парсинг временно доступен только для администраторов.\n"
                     "Ведутся технические работы по улучшению сервиса.\n\n"
                     "Приносим извинения за неудобства!",
        'admin_only': "👑 *Только для администраторов*\n\n"
                      "Парсинг временно доступен только администраторам.\n"
                      "Пожалуйста, подождите или создайте тикет.",
    },
    'en': {
        'start': "🇬🇧 Welcome to ParsTape!",
        'main': "📊 *ParsTape — Marketplace Expert*\n\nChoose an action:",
        'parsing_info': "🕸️ *Parsing WB & Ozon*\n\nEnter search query:",
        'parsing_limit': "📊 Enter items count (1-50):",
        'parsing_start': "🔄 Parsing started...\nPlease wait.",
        'parsing_done': "✅ Parsing completed!\nResults attached:",
        'no_results': "❌ No results for '{query}'",
        'wb_found': "📦 *Wildberries:* {count} items",
        'ozon_found': "📦 *Ozon:* {count} items",
        'invalid_limit': "❌ Enter 1-50",
        'settings': "⚙️ Settings",
        'support': "🆘 Support",
        'parsing_btn': "🕸️ Parsing",
        'back': "◀️ Back",
        'menu': "🏠 Menu",
        'change_lang': "🌐 Language",
        'create_ticket': "📝 Create ticket",
        'ticket_title': "📝 Enter ticket title:",
        'ticket_desc': "📄 Describe your problem:",
        'ticket_sent': "✅ Ticket sent!",
        'ticket_new': "📩 *NEW TICKET*\nFrom: {name}\nID: {user}\nTitle: {title}\nDesc: {desc}\n\n/reply {user} [text]",
        'reply_format': "📝 /reply USER_ID TEXT",
        'reply_sent': "✅ Reply sent",
        'reply_msg': "✉️ *Reply:*\n{text}\n\n/close_ticket",
        'ticket_closed': "✅ Ticket closed",
        'no_ticket': "❌ No active tickets",
        'ticket_closed_admin': "✅ Ticket for user {user} closed",
        'unknown': "❌ Unknown command",
        'admin_stats': "✅ *Admin Panel*\nTickets: {tickets}",
        'tech_work': "🔧 *Technical work*\nParsing temporarily for admins only.",
        'admin_only': "👑 *Admin only*\nParsing is temporarily for admins only.",
    }
}

user_lang: Dict[int, str] = {}
active_tickets: Dict[int, dict] = {}

# ==================== ПАРСЕР С ОБХОДОМ ЗАЩИТЫ ====================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }

async def parse_wildberries(query: str, limit: int):
    products = []
    try:
        # API Wildberries с обходом
        url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?appType=1&curr=rub&dest=-1257786&query={query}&resultset=catalog&sort=popular&spp=30&limit={limit}"
        
        headers = get_random_headers()
        headers['Accept'] = 'application/json'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
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
        # Прямой запрос к странице поиска Ozon
        url = f"https://www.ozon.ru/search/?text={query}"
        
        headers = get_random_headers()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    
                    # Ищем JSON данные в HTML
                    json_match = re.search(r'window\.__STATE__\s*=\s*({.*?});', html, re.DOTALL)
                    if json_match:
                        try:
                            data = json.loads(json_match.group(1))
                            # Ищем товары в JSON
                            for key in list(data.keys())[:20]:
                                if 'product' in key.lower() or 'card' in key.lower():
                                    item = data.get(key, {})
                                    name = item.get('title', '') or item.get('name', '')
                                    price_info = item.get('price', {})
                                    price = price_info.get('price', '') or price_info.get('value', '')
                                    if isinstance(price, str):
                                        price = re.sub(r'[^\d]', '', price)
                                    try:
                                        price = int(price) if price else 0
                                    except:
                                        price = 0
                                    if name and price > 0 and len(products) < limit:
                                        products.append({
                                            'name': name[:100],
                                            'price': price,
                                            'link': url
                                        })
                        except:
                            pass
                    
                    # Если JSON не помог, ищем простые карточки
                    if len(products) < limit:
                        # Поиск ссылок на товары
                        links = re.findall(r'href="(/product/[^"]+)"', html)
                        titles = re.findall(r'<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</span>', html)
                        
                        for i in range(min(len(links), len(titles), limit)):
                            if i < len(links) and i < len(titles):
                                name = titles[i].strip()
                                price = 0
                                # Поиск цены рядом
                                price_match = re.search(r'(\d[\d\s]*)\s*₽', html[max(0, html.find(name)-500):html.find(name)+500])
                                if price_match:
                                    price = int(re.sub(r'\s', '', price_match.group(1)))
                                if name and price > 0:
                                    products.append({
                                        'name': name[:100],
                                        'price': price,
                                        'link': f"https://www.ozon.ru{links[i]}"
                                    })
                else:
                    print(f"Ozon статус: {resp.status}")
    except Exception as e:
        print(f"Ozon ошибка: {e}")
    
    return products

async def parse_both(query: str, limit: int):
    print(f"🔍 Парсинг: {query}, лимит: {limit}")
    
    wb = await parse_wildberries(query, limit)
    await asyncio.sleep(random.uniform(1, 2))
    ozon = await parse_ozon(query, limit)
    
    print(f"WB: {len(wb)} товаров")
    print(f"Ozon: {len(ozon)} товаров")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = re.sub(r'[^\w\s-]', '', query).replace(' ', '_')
    files = {}
    
    # Сводка
    summary_file = f"ParsTape_Summary_{safe_query}_{timestamp}.csv"
    with open(summary_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['query', 'wb_count', 'ozon_count', 'total', 'date'])
        writer.writerow([query, len(wb), len(ozon), len(wb)+len(ozon), datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    files['summary'] = summary_file
    
    # Wildberries
    if wb:
        wb_file = f"ParsTape_WB_{safe_query}_{timestamp}.csv"
        with open(wb_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['№', 'Название', 'Цена (₽)', 'Ссылка'])
            for i, p in enumerate(wb, 1):
                writer.writerow([i, p['name'], p['price'], p['link']])
        files['wb'] = wb_file
    
    # Ozon
    if ozon:
        ozon_file = f"ParsTape_Ozon_{safe_query}_{timestamp}.csv"
        with open(ozon_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['№', 'Название', 'Цена (₽)', 'Ссылка'])
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

def get_support_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[lang]['create_ticket'], callback_data="create_ticket")],
        [InlineKeyboardButton(text=t[lang]['back'], callback_data="back")]
    ])

def get_cancel_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_ticket")]
    ])

def get_settings_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t[lang]['change_lang'], callback_data="change_lang")],
        [InlineKeyboardButton(text=t[lang]['back'], callback_data="back")]
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
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    
    # Проверка: только админы могут парсить
    if user_id not in ADMIN_IDS:
        await message.answer(t[lang]['admin_only'], parse_mode="Markdown")
        return
    
    await state.set_state(Form.waiting_query)
    await message.answer(t[lang]['parsing_info'], parse_mode="Markdown", reply_markup=get_back_keyboard(lang))

@dp.message(Form.waiting_query)
async def get_query(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    query = message.text.strip()
    
    await state.update_data(query=query)
    await message.answer(t[lang]['parsing_limit'], parse_mode="Markdown")
    await state.set_state(Form.waiting_limit)

@dp.message(Form.waiting_limit)
async def get_limit_and_parse(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    
    try:
        limit = int(message.text)
        if limit < 1 or limit > 50:
            await message.answer(t[lang]['invalid_limit'])
            return
        
        data = await state.get_data()
        query = data.get('query', '')
        
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
            
    except ValueError:
        await message.answer(t[lang]['invalid_limit'])

@dp.message(F.text.in_({'⚙️ Настройки', '⚙️ Settings'}))
async def settings_menu(message: Message):
    lang = user_lang.get(message.from_user.id, 'ru')
    await message.answer(t[lang]['settings'], parse_mode="Markdown", reply_markup=get_settings_keyboard(lang))

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
    
    active_tickets[user_id] = {'title': title, 'desc': desc, 'user': user_id, 'name': name}
    
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
        t[lang]['admin_stats'].format(tickets=len(active_tickets)),
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
    print("📌 Парсинг доступен только админам")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
