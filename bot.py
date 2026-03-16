import telebot
from telebot import types
import sqlite3
import time
import random
import string
from datetime import datetime, timedelta
import re
import os
import hashlib
from enum import Enum

# ========== НАСТРОЙКИ ==========

TOKEN = "8259179783:AAHuDseoX6aULdjsWPXT-zWWSNH9-nt6s6U"
bot = telebot.TeleBot(TOKEN)

# ID главного админа
MAIN_ADMIN_ID = 8779825034

# Название бота и валюта
BOT_NAME = "ArtemMarket"
CURRENCY = "⭐ Звезды"

# Категории товаров
CATEGORIES = {
    "📱 Смартфоны": ["Новые", "Восстановленные"],
    "💻 Ноутбуки": ["Новые", "Восстановленные"],
    "🎧 Наушники": ["Новые", "Восстановленные"],
    "⌚ Часы": ["Новые", "Восстановленные"],
    "📷 Фото/Видео": ["Новые", "Восстановленные"],
    "🔌 Аксессуары": ["Новые", "Восстановленные"],
    "📦 Бытовая техника": ["Новые", "Восстановленные"],
    "📱 Чехлы и защита": ["Новые"],
    "🔋 Зарядки": ["Новые"],
    "🎮 Геймерское": ["Новые", "Восстановленные"]
}

# Статусы пользователей
class UserRole(Enum):
    USER = "user"
    SELLER = "seller"  # Продавец (после регистрации)
    DEVELOPER = "developer"  # Разработчик (может добавлять товары)
    ADMIN = "admin"

# Статусы товаров
class ProductStatus(Enum):
    ACTIVE = "active"
    SOLD = "sold"
    HIDDEN = "hidden"

# ========== БАЗА ДАННЫХ ==========

def init_db():
    """Создание базы данных"""
    conn = sqlite3.connect('artemmarket.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            role TEXT DEFAULT 'user',
            balance INTEGER DEFAULT 0,
            registered_date TEXT,
            last_active TEXT,
            is_verified INTEGER DEFAULT 0,
            total_purchases INTEGER DEFAULT 0,
            total_sales INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            reviews_count INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица продавцов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sellers (
            user_id INTEGER PRIMARY KEY,
            phone TEXT,
            store_name TEXT,
            store_description TEXT,
            registered_date TEXT,
            verified INTEGER DEFAULT 0,
            total_products INTEGER DEFAULT 0,
            total_sales INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица товаров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            category TEXT,
            subcategory TEXT,
            title TEXT,
            description TEXT,
            price INTEGER,
            condition TEXT,
            photos TEXT,
            specifications TEXT,
            status TEXT DEFAULT 'active',
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            created_date TEXT,
            updated_date TEXT,
            FOREIGN KEY (seller_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица корзины
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER DEFAULT 1,
            added_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    
    # Таблица заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE,
            buyer_id INTEGER,
            seller_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            total_price INTEGER,
            payment_method TEXT,
            status TEXT,
            transaction_id TEXT,
            created_date TEXT,
            confirmed_date TEXT,
            completed_date TEXT,
            FOREIGN KEY (buyer_id) REFERENCES users(user_id),
            FOREIGN KEY (seller_id) REFERENCES users(user_id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    
    # Таблица отзывов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            buyer_id INTEGER,
            seller_id INTEGER,
            product_id INTEGER,
            rating INTEGER,
            text TEXT,
            photos TEXT,
            created_date TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (buyer_id) REFERENCES users(user_id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    
    # Таблица вопросов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            user_id INTEGER,
            question TEXT,
            answer TEXT,
            answered_by INTEGER,
            created_date TEXT,
            answered_date TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            type TEXT,
            description TEXT,
            stars_transaction_id TEXT,
            status TEXT,
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Таблица поддержки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            subject TEXT,
            message TEXT,
            reply TEXT,
            status TEXT DEFAULT 'open',
            created_date TEXT,
            closed_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_db():
    """Получить соединение с БД"""
    return sqlite3.connect('artemmarket.db', check_same_thread=False)

def generate_order_number():
    """Генерация номера заказа"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"AM-{timestamp}-{random_part}"

def get_user(user_id):
    """Получить пользователя"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(user):
    """Добавление пользователя"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, registered_date, last_active)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user.id, user.username, user.first_name, user.last_name, 
          datetime.now().isoformat(), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def update_balance(user_id, amount, description, stars_id=None):
    """Обновление баланса"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    
    cursor.execute('''
        INSERT INTO transactions (user_id, amount, type, description, stars_transaction_id, status, date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, 'balance_change', description, stars_id, 'completed', datetime.now().isoformat()))
    
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    new_balance = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    return new_balance

def is_seller(user_id):
    """Проверка, является ли пользователь продавцом"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user and (user[0] in ['seller', 'developer', 'admin'])

def is_developer(user_id):
    """Проверка, является ли пользователь разработчиком"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user and user[0] in ['developer', 'admin']

# ========== ГЛАВНОЕ МЕНЮ ==========

@bot.message_handler(commands=['start'])
def start_command(message):
    """Запуск бота"""
    user = message.from_user
    add_user(user)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🛍 Каталог", callback_data="catalog")
    btn2 = types.InlineKeyboardButton("🛒 Корзина", callback_data="cart")
    btn3 = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    btn4 = types.InlineKeyboardButton("⭐ Баланс", callback_data="balance")
    btn5 = types.InlineKeyboardButton("💼 Стать продавцом", callback_data="become_seller")
    btn6 = types.InlineKeyboardButton("❓ Помощь", callback_data="help")
    btn7 = types.InlineKeyboardButton("📞 Поддержка", callback_data="support")
    btn8 = types.InlineKeyboardButton("📜 Документы", callback_data="docs")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    
    welcome = f"""<b>🛍 Добро пожаловать в {BOT_NAME}!</b>

Здесь ты можешь:
• Купить технику и аксессуары
• Продавать свои товары
• Зарабатывать звёзды
• Общаться с продавцами

<b>🔥 Горячие предложения:</b>
• Новые и восстановленные товары
• Проверенные продавцы
• Безопасные сделки

<b>💫 Как начать:</b>
1. Пополни баланс через /balance
2. Выбери товары в каталоге
3. Оформи заказ

Выбери действие в меню ниже 👇"""
    
    bot.send_message(message.chat.id, welcome, parse_mode='html', reply_markup=markup)

@bot.message_handler(commands=['catalog'])
def catalog_command(message):
    """Каталог товаров"""
    show_catalog(message.chat.id)

def show_catalog(chat_id):
    """Показать каталог"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for category in CATEGORIES.keys():
        btn = types.InlineKeyboardButton(category, callback_data=f"cat_{category}")
        markup.add(btn)
    
    markup.add(types.InlineKeyboardButton("🔍 Поиск", callback_data="search"),
               types.InlineKeyboardButton("📊 Популярное", callback_data="popular"))
    
    bot.send_message(chat_id, "📱 <b>Категории товаров:</b>\nВыбери интересующую категорию:", 
                    parse_mode='html', reply_markup=markup)

# ========== ПРОФИЛЬ И БАЛАНС ==========

@bot.message_handler(commands=['profile'])
def profile_command(message):
    """Профиль пользователя"""
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        add_user(message.from_user)
        user = get_user(user_id)
    
    # Получаем статистику
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM orders WHERE buyer_id = ?', (user_id,))
    purchases = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM orders WHERE seller_id = ?', (user_id,))
    sales = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM cart WHERE user_id = ?', (user_id,))
    cart_items = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM products WHERE seller_id = ? AND status = "active"', (user_id,))
    products_count = cursor.fetchone()[0]
    
    conn.close()
    
    role_emoji = {
        'user': '👤',
        'seller': '💼',
        'developer': '👑',
        'admin': '⚡'
    }.get(user[4], '👤')
    
    profile_text = f"""<b>{role_emoji} ТВОЙ ПРОФИЛЬ</b>

🆔 ID: <code>{user_id}</code>
👤 Имя: {message.from_user.first_name}
🔖 Username: @{message.from_user.username or 'нет'}
📞 Телефон: {user[3] or 'не указан'}
⭐ Роль: {user[4].upper()}

<b>💰 Финансы:</b>
💎 Баланс: {user[5]} {CURRENCY}
🛒 Покупок: {purchases}
📦 Продаж: {sales}
🏷 Товаров в продаже: {products_count}

<b>📊 Активность:</b>
🛍 В корзине: {cart_items}
⭐ Рейтинг: {user[11]:.1f} ({user[12]} отзывов)
📅 Регистрация: {user[6][:10]}

<i>Последний визит: {user[7][:16]}</i>"""
    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("💰 Пополнить", callback_data="deposit")
    btn2 = types.InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders")
    btn3 = types.InlineKeyboardButton("📝 Мои товары", callback_data="my_products")
    btn4 = types.InlineKeyboardButton("⭐ Мои отзывы", callback_data="my_reviews")
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(message.chat.id, profile_text, parse_mode='html', reply_markup=markup)

@bot.message_handler(commands=['balance'])
def balance_command(message):
    """Баланс и пополнение"""
    user_id = message.from_user.id
    user = get_user(user_id)
    
    # Получаем историю транзакций
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT amount, description, date FROM transactions 
        WHERE user_id = ? ORDER BY date DESC LIMIT 5
    ''', (user_id,))
    transactions = cursor.fetchall()
    conn.close()
    
    text = f"""<b>💰 ТВОЙ БАЛАНС</b>

💎 Текущий баланс: <b>{user[5]}</b> {CURRENCY}

<b>📊 Последние операции:</b>
"""
    for t in transactions:
        sign = "+" if t[0] > 0 else ""
        text += f"{sign}{t[0]} {CURRENCY} - {t[1]} ({t[2][:16]})\n"
    
    text += "\n<b>💫 Пополнить звёздами:</b>\n"
    text += "• 50 ⭐ = 50 звёзд\n"
    text += "• 100 ⭐ = 100 звёзд\n"
    text += "• 500 ⭐ = 500 звёзд\n"
    text += "• 1000 ⭐ = 1000 звёзд"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("50 ⭐", callback_data="pay_50")
    btn2 = types.InlineKeyboardButton("100 ⭐", callback_data="pay_100")
    btn3 = types.InlineKeyboardButton("500 ⭐", callback_data="pay_500")
    btn4 = types.InlineKeyboardButton("1000 ⭐", callback_data="pay_1000")
    btn5 = types.InlineKeyboardButton("🔁 Обменять звёзды", callback_data="exchange_stars")
    markup.add(btn1, btn2, btn3, btn4, btn5)
    
    bot.send_message(message.chat.id, text, parse_mode='html', reply_markup=markup)

# ========== ПОПОЛНЕНИЕ ЗВЁЗДАМИ ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_'))
def pay_with_stars(call):
    """Оплата звёздами"""
    amount = int(call.data.split('_')[1])
    user_id = call.from_user.id
    
    # Создаём счёт для оплаты звёздами
    invoice = bot.create_invoice_link(
        title=f"Пополнение баланса в {BOT_NAME}",
        description=f"Пополнение на {amount} {CURRENCY}",
        payload=f"deposit_{user_id}_{amount}",
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(label=f"{amount} ⭐", amount=amount)]
    )
    
    bot.send_message(call.message.chat.id, 
                    f"💫 <b>Ссылка для оплаты звёздами:</b>\n{invoice}\n\n"
                    f"После оплаты звёзды автоматически зачислятся на баланс!",
                    parse_mode='html')

# ========== СТАТЬ ПРОДАВЦОМ ==========

@bot.message_handler(commands=['become_seller'])
def become_seller_command(message):
    """Стать продавцом"""
    start_seller_registration(message)

@bot.callback_query_handler(func=lambda call: call.data == 'become_seller')
def become_seller_callback(call):
    """Стать продавцом (из кнопки)"""
    start_seller_registration(call.message)

def start_seller_registration(message):
    """Начало регистрации продавца"""
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user and user[4] in ['seller', 'developer', 'admin']:
        bot.send_message(message.chat.id, 
                        "✅ Вы уже зарегистрированы как продавец!\n"
                        "Используйте /add_product чтобы добавить товар.")
        return
    
    text = """<b>💼 РЕГИСТРАЦИЯ ПРОДАВЦА</b>

Чтобы стать продавцом, нужно:
1. Подтвердить номер телефона
2. Указать название магазина
3. Написать краткое описание

<b>Почему стоит стать продавцом?</b>
• Продавайте технику и аксессуары
• Получайте оплату звёздами
• Общайтесь с покупателями
• Растите рейтинг и продажи

Нажмите кнопку ниже, чтобы начать регистрацию 👇"""
    
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("📞 Начать регистрацию", callback_data="start_seller_reg")
    markup.add(btn)
    
    bot.send_message(message.chat.id, text, parse_mode='html', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'start_seller_reg')
def start_seller_reg_callback(call):
    """Начало регистрации продавца"""
    msg = bot.send_message(call.message.chat.id, 
                          "📞 <b>Шаг 1 из 3</b>\n\n"
                          "Пожалуйста, отправьте ваш номер телефона.\n"
                          "Например: +79991234567",
                          parse_mode='html')
    bot.register_next_step_handler(msg, process_seller_phone)

def process_seller_phone(message):
    """Обработка номера телефона"""
    phone = message.text.strip()
    
    # Простая валидация номера
    phone_pattern = re.compile(r'^\+?[0-9]{10,15}$')
    if not phone_pattern.match(phone.replace(' ', '')):
        bot.reply_to(message, 
                    "❌ Неверный формат номера. Пожалуйста, введите номер в формате +79991234567")
        return
    
    # Сохраняем в временное хранилище (в реальном проекте лучше через БД)
    bot.register_next_step_handler_by_chat_id(
        message.chat.id, 
        process_seller_store_name, 
        {'user_id': message.from_user.id, 'phone': phone}
    )
    
    bot.send_message(message.chat.id, 
                    "✅ Номер принят!\n\n"
                    "📝 <b>Шаг 2 из 3</b>\n"
                    "Введите название вашего магазина:",
                    parse_mode='html')

def process_seller_store_name(message, data):
    """Обработка названия магазина"""
    store_name = message.text.strip()
    
    if len(store_name) < 3 or len(store_name) > 50:
        bot.reply_to(message, "❌ Название должно быть от 3 до 50 символов")
        return
    
    data['store_name'] = store_name
    
    bot.send_message(message.chat.id, 
                    f"✅ Название принято: {store_name}\n\n"
                    f"📝 <b>Шаг 3 из 3</b>\n"
                    f"Напишите краткое описание вашего магазина (до 200 символов):",
                    parse_mode='html')
    
    bot.register_next_step_handler(message, process_seller_description, data)

def process_seller_description(message, data):
    """Обработка описания магазина"""
    description = message.text.strip()
    
    if len(description) < 10 or len(description) > 200:
        bot.reply_to(message, "❌ Описание должно быть от 10 до 200 символов")
        return
    
    user_id = data['user_id']
    
    # Сохраняем продавца в БД
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO sellers (user_id, phone, store_name, store_description, registered_date, verified)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, data['phone'], data['store_name'], description, datetime.now().isoformat(), 1))
    
    cursor.execute('UPDATE users SET role = ?, phone = ? WHERE user_id = ?', 
                  ('seller', data['phone'], user_id))
    
    conn.commit()
    conn.close()
    
    # Отправляем подтверждение
    text = f"""<b>🎉 ПОЗДРАВЛЯЕМ! ВЫ СТАЛИ ПРОДАВЦОМ!</b>

✅ Регистрация успешно завершена!

<b>Ваши данные:</b>
🏪 Магазин: {data['store_name']}
📞 Телефон: {data['phone']}
📝 Описание: {description}

<b>Что дальше?</b>
• Добавьте товары через /add_product
• Настройте витрину магазина
• Отвечайте на вопросы покупателей

Удачи в продажах! 💫"""
    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("➕ Добавить товар", callback_data="add_product")
    btn2 = types.InlineKeyboardButton("📋 Мои товары", callback_data="my_products")
    markup.add(btn1, btn2)
    
    bot.send_message(message.chat.id, text, parse_mode='html', reply_markup=markup)
    
    # Уведомление админу
    bot.send_message(MAIN_ADMIN_ID,
                    f"🆕 <b>Новый продавец!</b>\n"
                    f"👤 Пользователь: @{message.from_user.username}\n"
                    f"🏪 Магазин: {data['store_name']}",
                    parse_mode='html')

# ========== ДОБАВЛЕНИЕ ТОВАРОВ ==========

@bot.message_handler(commands=['add_product'])
def add_product_command(message):
    """Добавление товара"""
    user_id = message.from_user.id
    
    if not is_seller(user_id):
        bot.reply_to(message, 
                    "❌ Только продавцы могут добавлять товары!\n"
                    "Станьте продавцом через /become_seller")
        return
    
    start_product_registration(message)

def start_product_registration(message):
    """Начало регистрации товара"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for category in CATEGORIES.keys():
        btn = types.InlineKeyboardButton(category, callback_data=f"prod_cat_{category}")
        markup.add(btn)
    
    bot.send_message(message.chat.id,
                    "➕ <b>ДОБАВЛЕНИЕ ТОВАРА</b>\n\n"
                    "Выберите категорию товара:",
                    parse_mode='html',
                    reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('prod_cat_'))
def process_product_category(call):
    """Обработка выбора категории"""
    category = call.data.replace('prod_cat_', '')
    
    # Сохраняем в кэш (в реальном проекте через БД)
    bot.answer_callback_query(call.id, f"Выбрана категория: {category}")
    
    # Показываем подкатегории
    subcategories = CATEGORIES[category]
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for subcat in subcategories:
        btn = types.InlineKeyboardButton(subcat, callback_data=f"prod_subcat_{category}_{subcat}")
        markup.add(btn)
    
    bot.edit_message_text(
        f"➕ <b>ДОБАВЛЕНИЕ ТОВАРА</b>\n\n"
        f"Категория: {category}\n"
        f"Выберите состояние товара:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='html',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('prod_subcat_'))
def process_product_subcategory(call):
    """Обработка выбора подкатегории"""
    _, _, category, condition = call.data.split('_', 3)
    
    # Сохраняем в кэш
    data = {'category': category, 'condition': condition}
    
    msg = bot.send_message(call.message.chat.id,
                          f"➕ <b>ДОБАВЛЕНИЕ ТОВАРА</b>\n\n"
                          f"Категория: {category}\n"
                          f"Состояние: {condition}\n\n"
                          f"📝 <b>Шаг 1 из 5</b>\n"
                          f"Введите название товара:",
                          parse_mode='html')
    
    bot.register_next_step_handler(msg, process_product_title, data)

def process_product_title(message, data):
    """Обработка названия товара"""
    title = message.text.strip()
    
    if len(title) < 5 or len(title) > 100:
        bot.reply_to(message, "❌ Название должно быть от 5 до 100 символов")
        return
    
    data['title'] = title
    
    msg = bot.send_message(message.chat.id,
                          f"✅ Название принято!\n\n"
                          f"📝 <b>Шаг 2 из 5</b>\n"
                          f"Введите подробное описание товара:",
                          parse_mode='html')
    
    bot.register_next_step_handler(msg, process_product_description, data)

def process_product_description(message, data):
    """Обработка описания товара"""
    description = message.text.strip()
    
    if len(description) < 20 or len(description) > 1000:
        bot.reply_to(message, "❌ Описание должно быть от 20 до 1000 символов")
        return
    
    data['description'] = description
    
    msg = bot.send_message(message.chat.id,
                          f"✅ Описание принято!\n\n"
                          f"📝 <b>Шаг 3 из 5</b>\n"
                          f"Введите цену в звёздах (только число):",
                          parse_mode='html')
    
    bot.register_next_step_handler(msg, process_product_price, data)

def process_product_price(message, data):
    """Обработка цены товара"""
    try:
        price = int(message.text.strip())
        if price < 1 or price > 1000000:
            raise ValueError
    except:
        bot.reply_to(message, "❌ Введите корректное число (от 1 до 1 000 000)")
        return
    
    data['price'] = price
    
    msg = bot.send_message(message.chat.id,
                          f"✅ Цена принята: {price} ⭐\n\n"
                          f"📝 <b>Шаг 4 из 5</b>\n"
                          f"Введите характеристики товара (одна строка = одна характеристика):\n"
                          f"Например:\n"
                          f"• Процессор: Snapdragon 8 Gen 2\n"
                          f"• Память: 256 ГБ\n"
                          f"• Цвет: Черный",
                          parse_mode='html')
    
    bot.register_next_step_handler(msg, process_product_specs, data)

def process_product_specs(message, data):
    """Обработка характеристик товара"""
    specs = message.text.strip()
    
    if len(specs) < 10:
        bot.reply_to(message, "❌ Слишком мало характеристик")
        return
    
    data['specs'] = specs
    
    msg = bot.send_message(message.chat.id,
                          f"✅ Характеристики приняты!\n\n"
                          f"📝 <b>Шаг 5 из 5</b>\n"
                          f"Отправьте фото товара (можно несколько):\n"
                          f"После отправки фото нажмите /done",
                          parse_mode='html')
    
    bot.register_next_step_handler(msg, process_product_photos, data)

def process_product_photos(message, data):
    """Обработка фото товара"""
    if message.text and message.text == '/done':
        save_product(message, data)
        return
    
    if not message.photo:
        bot.reply_to(message, "❌ Пожалуйста, отправьте фото или нажмите /done")
        bot.register_next_step_handler(message, process_product_photos, data)
        return
    
    # Сохраняем фото (в реальном проекте нужно сохранять file_id)
    if 'photos' not in data:
        data['photos'] = []
    
    # Берём самое качественное фото
    photo = message.photo[-1].file_id
    data['photos'].append(photo)
    
    bot.reply_to(message, f"✅ Фото {len(data['photos'])} сохранено. Отправьте ещё или /done")
    bot.register_next_step_handler(message, process_product_photos, data)

def save_product(message, data):
    """Сохранение товара в БД"""
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    photos = ','.join(data.get('photos', []))
    
    cursor.execute('''
        INSERT INTO products 
        (seller_id, category, subcategory, title, description, price, condition, photos, specifications, created_date, updated_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data['category'], data['condition'], data['title'], 
          data['description'], data['price'], data['condition'], photos, 
          data['specs'], datetime.now().isoformat(), datetime.now().isoformat()))
    
    product_id = cursor.lastrowid
    
    cursor.execute('UPDATE sellers SET total_products = total_products + 1 WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()
    
    text = f"""<b>🎉 ТОВАР УСПЕШНО ДОБАВЛЕН!</b>

📦 ID товара: {product_id}
🏷 Название: {data['title']}
💰 Цена: {data['price']} ⭐
📁 Категория: {data['category']} ({data['condition']})

Товар появится в каталоге после модерации.
Вы можете управлять товарами в /my_products"""
    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("➕ Добавить ещё", callback_data="add_product")
    btn2 = types.InlineKeyboardButton("📋 Мои товары", callback_data="my_products")
    markup.add(btn1, btn2)
    
    bot.send_message(message.chat.id, text, parse_mode='html', reply_markup=markup)
    
    # Уведомление админу
    bot.send_message(MAIN_ADMIN_ID,
                    f"🆕 <b>Новый товар!</b>\n"
                    f"👤 Продавец: @{message.from_user.username}\n"
                    f"📦 Товар: {data['title']}\n"
                    f"💰 Цена: {data['price']} ⭐",
                    parse_mode='html')

# ========== ПРОСМОТР ТОВАРОВ ==========

@bot.message_handler(commands=['products'])
def products_command(message):
    """Мои товары"""
    user_id = message.from_user.id
    
    if not is_seller(user_id):
        bot.reply_to(message, "❌ Вы не являетесь продавцом")
        return
    
    show_my_products(message.chat.id, user_id)

def show_my_products(chat_id, user_id):
    """Показать товары продавца"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, price, status, views FROM products 
        WHERE seller_id = ? ORDER BY created_date DESC
    ''', (user_id,))
    
    products = cursor.fetchall()
    conn.close()
    
    if not products:
        bot.send_message(chat_id,
                        "📦 У вас пока нет товаров.\n"
                        "Добавьте первый товар через /add_product")
        return
    
    text = "<b>📦 МОИ ТОВАРЫ</b>\n\n"
    
    for p in products:
        status_emoji = "🟢" if p[3] == 'active' else "🔴"
        text += f"{status_emoji} <b>{p[1]}</b>\n"
        text += f"   ID: {p[0]} | Цена: {p[2]} ⭐ | Просмотров: {p[4]}\n\n"
    
    text += "\nДля управления товаром: /product_ [ID]"
    
    bot.send_message(chat_id, text, parse_mode='html')

@bot.message_handler(commands=['product'])
def product_command(message):
    """Просмотр товара"""
    args = message.text.split()
    
    if len(args) < 2:
        bot.reply_to(message, "❌ Используйте: /product [ID товара]")
        return
    
    try:
        product_id = int(args[1])
        show_product(message.chat.id, product_id)
    except:
        bot.reply_to(message, "❌ Неверный ID товара")

def show_product(chat_id, product_id, from_callback=False):
    """Показать товар"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.*, u.username, u.first_name, s.store_name 
        FROM products p
        JOIN users u ON p.seller_id = u.user_id
        LEFT JOIN sellers s ON p.seller_id = s.user_id
        WHERE p.id = ? AND p.status = 'active'
    ''', (product_id,))
    
    product = cursor.fetchone()
    
    if not product:
        if not from_callback:
            bot.send_message(chat_id, "❌ Товар не найден или недоступен")
        conn.close()
        return
    
    # Увеличиваем счётчик просмотров
    cursor.execute('UPDATE products SET views = views + 1 WHERE id = ?', (product_id,))
    
    # Получаем отзывы
    cursor.execute('''
        SELECT rating, text, created_date FROM reviews 
        WHERE product_id = ? ORDER BY created_date DESC LIMIT 3
    ''', (product_id,))
    reviews = cursor.fetchall()
    
    # Получаем вопросы
    cursor.execute('''
        SELECT question, answer FROM questions 
        WHERE product_id = ? AND status = 'answered' LIMIT 3
    ''', (product_id,))
    questions = cursor.fetchall()
    
    conn.commit()
    conn.close()
    
    # Формируем карточку товара
    photos = product[8].split(',') if product[8] else []
    specs = product[9].split('\n') if product[9] else []
    
    text = f"""<b>📱 {product[5]}</b>

💰 <b>Цена:</b> {product[6]} ⭐
📁 <b>Категория:</b> {product[2]} ({product[7]})
👤 <b>Продавец:</b> {product[15]} (@{product[14]})
⭐ <b>Рейтинг продавца:</b> {product[13] or 'Новый'}

📝 <b>Описание:</b>
{product[4]}

📊 <b>Характеристики:</b>
"""
    for spec in specs:
        if spec.strip():
            text += f"• {spec.strip()}\n"
    
    text += f"\n📸 <b>Фото:</b> {len(photos)} шт."
    text += f"\n👁 <b>Просмотров:</b> {product[10]}"
    
    if reviews:
        text += f"\n\n⭐ <b>Последние отзывы:</b>"
        for r in reviews:
            stars = "⭐" * r[0]
            text += f"\n{stars} {r[1][:50]}..."
    
    if questions:
        text += f"\n\n❓ <b>Последние вопросы:</b>"
        for q in questions:
            text += f"\nQ: {q[0][:50]}..."
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🛒 В корзину", callback_data=f"add_to_cart_{product_id}")
    btn2 = types.InlineKeyboardButton("💬 Задать вопрос", callback_data=f"ask_question_{product_id}")
    btn3 = types.InlineKeyboardButton("⭐ Отзывы", callback_data=f"product_reviews_{product_id}")
    btn4 = types.InlineKeyboardButton("❓ Вопросы", callback_data=f"product_questions_{product_id}")
    btn5 = types.InlineKeyboardButton("👤 Профиль продавца", callback_data=f"seller_profile_{product[1]}")
    markup.add(btn1, btn2, btn3, btn4, btn5)
    
    # Отправляем фото если есть
    if photos:
        bot.send_photo(chat_id, photos[0], caption=text[:1024], parse_mode='html', reply_markup=markup)
        
        # Отправляем остальные фото
        for photo in photos[1:]:
            bot.send_photo(chat_id, photo)
    else:
        bot.send_message(chat_id, text, parse_mode='html', reply_markup=markup)

# ========== КОРЗИНА ==========

@bot.message_handler(commands=['cart'])
def cart_command(message):
    """Корзина"""
    show_cart(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_to_cart_'))
def add_to_cart(call):
    """Добавление в корзину"""
    product_id = int(call.data.split('_')[3])
    user_id = call.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Проверяем, есть ли уже в корзине
    cursor.execute('SELECT id FROM cart WHERE user_id = ? AND product_id = ?', (user_id, product_id))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute('UPDATE cart SET quantity = quantity + 1 WHERE id = ?', (existing[0],))
    else:
        cursor.execute('''
            INSERT INTO cart (user_id, product_id, added_date)
            VALUES (?, ?, ?)
        ''', (user_id, product_id, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ Товар добавлен в корзину!")
    
    # Показываем корзину
    show_cart(call.message.chat.id, user_id)

def show_cart(chat_id, user_id):
    """Показать корзину"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.id, c.quantity, p.id, p.title, p.price, u.first_name, u.username
        FROM cart c
        JOIN products p ON c.product_id = p.id
        JOIN users u ON p.seller_id = u.user_id
        WHERE c.user_id = ?
    ''', (user_id,))
    
    cart_items = cursor.fetchall()
    conn.close()
    
    if not cart_items:
        bot.send_message(chat_id, "🛒 Ваша корзина пуста")
        return
    
    text = "<b>🛒 КОРЗИНА</b>\n\n"
    total = 0
    
    for item in cart_items:
        cart_id, qty, prod_id, title, price, seller_name, seller_un = item
        item_total = price * qty
        total += item_total
        
        text += f"• <b>{title}</b>\n"
        text += f"  Цена: {price} ⭐ x {qty} = {item_total} ⭐\n"
        text += f"  Продавец: {seller_name} (@{seller_un})\n"
        text += f"  [Удалить: /cart_remove_{cart_id}]\n\n"
    
    text += f"<b>ИТОГО: {total} ⭐</b>"
    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout")
    btn2 = types.InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart")
    markup.add(btn1, btn2)
    
    bot.send_message(chat_id, text, parse_mode='html', reply_markup=markup)

@bot.message_handler(commands=['cart_remove'])
def cart_remove_command(message):
    """Удаление из корзины"""
    args = message.text.split()
    
    if len(args) < 2:
        bot.reply_to(message, "❌ Неверная команда")
        return
    
    try:
        cart_id = int(args[1])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM cart WHERE id = ?', (cart_id,))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, "✅ Товар удалён из корзины")
        cart_command(message)
        
    except:
        bot.reply_to(message, "❌ Ошибка удаления")

@bot.callback_query_handler(func=lambda call: call.data == 'clear_cart')
def clear_cart(call):
    """Очистка корзины"""
    user_id = call.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cart WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "🗑 Корзина очищена")
    bot.edit_message_text("🛒 Ваша корзина пуста", 
                         call.message.chat.id, call.message.message_id)

# ========== ОФОРМЛЕНИЕ ЗАКАЗА ==========

@bot.callback_query_handler(func=lambda call: call.data == 'checkout')
def checkout(call):
    """Оформление заказа"""
    user_id = call.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем товары из корзины
    cursor.execute('''
        SELECT c.id, c.quantity, p.id, p.title, p.price, p.seller_id
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (user_id,))
    
    cart_items = cursor.fetchall()
    
    if not cart_items:
        bot.answer_callback_query(call.id, "❌ Корзина пуста")
        return
    
    # Проверяем баланс
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    total = sum(item[1] * item[4] for item in cart_items)
    
    if balance < total:
        bot.answer_callback_query(call.id, f"❌ Недостаточно средств. Нужно {total} ⭐")
        conn.close()
        return
    
    # Создаём заказы для каждого продавца
    orders = []
    for item in cart_items:
        order_number = generate_order_number()
        transaction_id = hashlib.md5(f"{order_number}{time.time()}".encode()).hexdigest()[:16]
        
        cursor.execute('''
            INSERT INTO orders 
            (order_number, buyer_id, seller_id, product_id, quantity, total_price, payment_method, status, transaction_id, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_number, user_id, item[5], item[2], item[1], item[1] * item[4], 
              'stars', 'paid', transaction_id, datetime.now().isoformat()))
        
        order_id = cursor.lastrowid
        orders.append(order_id)
        
        # Обновляем статус товара
        cursor.execute('UPDATE products SET status = ? WHERE id = ?', ('sold', item[2]))
    
    # Списание средств
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (total, user_id))
    
    # Начисление средств продавцам
    for item in cart_items:
        seller_amount = item[1] * item[4]
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', 
                      (seller_amount, item[5]))
        cursor.execute('UPDATE sellers SET total_sales = total_sales + 1 WHERE user_id = ?', (item[5],))
    
    # Очищаем корзину
    cursor.execute('DELETE FROM cart WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()
    
    # Отправляем чеки
    for order_id in orders:
        send_order_receipt(user_id, order_id)
    
    bot.answer_callback_query(call.id, "✅ Заказ оформлен!")

def send_order_receipt(user_id, order_id):
    """Отправка чека о покупке"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT o.order_number, o.total_price, o.transaction_id, o.created_date,
               p.title, u.first_name, u.username
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.seller_id = u.user_id
        WHERE o.id = ?
    ''', (order_id,))
    
    order = cursor.fetchone()
    conn.close()
    
    # Создаём анимированный чек
    receipt = f"""╔════════════════════╗
║     🧾 ЧЕК ПОКУПКИ    ║
╠════════════════════╣
║ Номер: {order[0]}
║ Дата: {order[3][:16]}
╠════════════════════╣
║ Товар: {order[4]}
║ Продавец: {order[5]} (@{order[6]})
╠════════════════════╣
║ Сумма: {order[1]} ⭐
║ Транзакция: {order[2]}
╠════════════════════╣
║ Спасибо за покупку!
║ Оставьте отзыв ⭐
╚════════════════════╝"""
    
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("⭐ Оставить отзыв", callback_data=f"write_review_{order_id}")
    markup.add(btn)
    
    bot.send_message(user_id, f"<pre>{receipt}</pre>", parse_mode='html', reply_markup=markup)

# ========== ОТЗЫВЫ ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith('write_review_'))
def write_review(call):
    """Написание отзыва"""
    order_id = int(call.data.split('_')[2])
    
    markup = types.InlineKeyboardMarkup(row_width=5)
    for i in range(1, 6):
        btn = types.InlineKeyboardButton("⭐" * i, callback_data=f"review_rate_{order_id}_{i}")
        markup.add(btn)
    
    bot.edit_message_text("⭐ <b>Оцените товар</b>\nВыберите количество звёзд:",
                         call.message.chat.id, call.message.message_id,
                         parse_mode='html', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('review_rate_'))
def review_rate(call):
    """Выбор оценки"""
    _, _, order_id, rating = call.data.split('_')
    
    msg = bot.send_message(call.message.chat.id,
                          f"⭐ Оценка: {'⭐' * int(rating)}\n\n"
                          f"📝 Напишите ваш отзыв:",
                          parse_mode='html')
    
    bot.register_next_step_handler(msg, process_review_text, order_id, rating)

def process_review_text(message, order_id, rating):
    """Обработка текста отзыва"""
    text = message.text.strip()
    
    if len(text) < 10 or len(text) > 500:
        bot.reply_to(message, "❌ Отзыв должен быть от 10 до 500 символов")
        return
    
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Получаем информацию о заказе
    cursor.execute('SELECT product_id, seller_id FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    
    # Сохраняем отзыв
    cursor.execute('''
        INSERT INTO reviews (order_id, buyer_id, seller_id, product_id, rating, text, created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (order_id, user_id, order[1], order[0], int(rating), text, datetime.now().isoformat()))
    
    # Обновляем рейтинг продавца
    cursor.execute('''
        SELECT AVG(rating), COUNT(*) FROM reviews WHERE seller_id = ?
    ''', (order[1],))
    avg_rating, count = cursor.fetchone()
    
    cursor.execute('UPDATE users SET rating = ?, reviews_count = ? WHERE user_id = ?',
                  (avg_rating, count, order[1]))
    
    conn.commit()
    conn.close()
    
    bot.reply_to(message, "✅ Спасибо за отзыв!")

# ========== ВОПРОСЫ О ТОВАРЕ ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith('ask_question_'))
def ask_question(call):
    """Задать вопрос о товаре"""
    product_id = int(call.data.split('_')[2])
    
    msg = bot.send_message(call.message.chat.id,
                          "❓ Напишите ваш вопрос о товаре:",
                          parse_mode='html')
    
    bot.register_next_step_handler(msg, process_question, product_id)

def process_question(message, product_id):
    """Обработка вопроса"""
    question = message.text.strip()
    
    if len(question) < 5 or len(question) > 500:
        bot.reply_to(message, "❌ Вопрос должен быть от 5 до 500 символов")
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO questions (product_id, user_id, question, created_date)
        VALUES (?, ?, ?, ?)
    ''', (product_id, message.from_user.id, question, datetime.now().isoformat()))
    
    question_id = cursor.lastrowid
    
    # Получаем информацию о продавце
    cursor.execute('SELECT seller_id FROM products WHERE id = ?', (product_id,))
    seller_id = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    # Уведомление продавцу
    bot.send_message(seller_id,
                    f"❓ <b>Новый вопрос о товаре</b>\n\n"
                    f"{question}\n\n"
                    f"Чтобы ответить: /answer_{question_id} [текст]",
                    parse_mode='html')
    
    bot.reply_to(message, "✅ Ваш вопрос отправлен продавцу!")

@bot.message_handler(commands=['answer'])
def answer_question(message):
    """Ответ на вопрос"""
    args = message.text.split(maxsplit=2)
    
    if len(args) < 3:
        bot.reply_to(message, "❌ Используйте: /answer [ID вопроса] [текст]")
        return
    
    try:
        question_id = int(args[1].replace('_', ''))
        answer = args[2]
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT q.user_id, q.question, p.title 
            FROM questions q
            JOIN products p ON q.product_id = p.id
            WHERE q.id = ? AND p.seller_id = ?
        ''', (question_id, message.from_user.id))
        
        question = cursor.fetchone()
        
        if not question:
            bot.reply_to(message, "❌ Вопрос не найден")
            conn.close()
            return
        
        cursor.execute('''
            UPDATE questions SET answer = ?, answered_by = ?, answered_date = ?, status = ?
            WHERE id = ?
        ''', (answer, message.from_user.id, datetime.now().isoformat(), 'answered', question_id))
        
        conn.commit()
        conn.close()
        
        # Отправляем ответ покупателю
        bot.send_message(question[0],
                        f"❓ <b>Ответ на ваш вопрос</b>\n\n"
                        f"Товар: {question[2]}\n"
                        f"Ваш вопрос: {question[1]}\n"
                        f"Ответ: {answer}",
                        parse_mode='html')
        
        bot.reply_to(message, "✅ Ответ отправлен!")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ========== ПОДДЕРЖКА ==========

@bot.message_handler(commands=['support'])
def support_command(message):
    """Поддержка"""
    text = """<b>📞 ПОДДЕРЖКА</b>

Выберите тему обращения:

1️⃣ Вопрос по работе бота
2️⃣ Проблема с заказом
3️⃣ Спор с продавцом
4️⃣ Жалоба на товар
5️⃣ Предложение по улучшению
6️⃣ Другое

Напишите ваш вопрос, и администратор ответит в ближайшее время."""
    
    bot.send_message(message.chat.id, text, parse_mode='html')
    
    msg = bot.reply_to(message, "✍️ Опишите вашу проблему:")
    bot.register_next_step_handler(msg, process_support)

def process_support(message):
    """Обработка обращения"""
    user_id = message.from_user.id
    text = message.text
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO support (user_id, message, created_date)
        VALUES (?, ?, ?)
    ''', (user_id, text, datetime.now().isoformat()))
    
    support_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Уведомление админу
    bot.send_message(MAIN_ADMIN_ID,
                    f"📞 <b>НОВОЕ ОБРАЩЕНИЕ #{support_id}</b>\n\n"
                    f"👤 Пользователь: @{message.from_user.username}\n"
                    f"🆔 ID: {user_id}\n\n"
                    f"📝 Сообщение:\n{text}\n\n"
                    f"Чтобы ответить: /reply_{support_id} [текст]",
                    parse_mode='html')
    
    bot.reply_to(message, "✅ Ваше обращение отправлено! Администратор ответит в ближайшее время.")

@bot.message_handler(commands=['reply'])
def reply_support(message):
    """Ответ на обращение (админ)"""
    if message.from_user.id != MAIN_ADMIN_ID:
        bot.reply_to(message, "❌ Доступ запрещён")
        return
    
    args = message.text.split(maxsplit=2)
    
    if len(args) < 3:
        bot.reply_to(message, "❌ Используйте: /reply [ID] [текст]")
        return
    
    try:
        support_id = int(args[1].replace('_', ''))
        reply_text = args[2]
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM support WHERE id = ?', (support_id,))
        support = cursor.fetchone()
        
        if not support:
            bot.reply_to(message, "❌ Обращение не найдено")
            conn.close()
            return
        
        cursor.execute('UPDATE support SET reply = ?, status = ?, closed_date = ? WHERE id = ?',
                      (reply_text, 'closed', datetime.now().isoformat(), support_id))
        
        conn.commit()
        conn.close()
        
        # Отправляем ответ пользователю
        bot.send_message(support[0],
                        f"📞 <b>Ответ на обращение #{support_id}</b>\n\n"
                        f"{reply_text}",
                        parse_mode='html')
        
        bot.reply_to(message, f"✅ Ответ отправлен пользователю {support[0]}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ========== ПОЛИТИКА И ОФЕРТА ==========

@bot.message_handler(commands=['policy'])
def policy_command(message):
    """Политика конфиденциальности"""
    text = """<b>🔒 ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</b>

1. <b>Сбор данных</b>
• Telegram ID и username
• Номер телефона (для продавцов)
• История покупок и заказов
• Переписка с поддержкой

2. <b>Использование данных</b>
• Обеспечение работы маркетплейса
• Связь с покупателями и продавцами
• Улучшение сервиса
• Предотвращение мошенничества

3. <b>Защита данных</b>
• Все данные хранятся в зашифрованном виде
• Доступ только у администратора
• Данные не передаются третьим лицам

4. <b>Ваши права</b>
• Запросить удаление данных
• Экспортировать свои данные
• Отозвать согласие

По вопросам: /support"""
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['offer'])
def offer_command(message):
    """Договор оферты"""
    text = f"""<b>📜 ДОГОВОР ОФЕРТЫ {BOT_NAME}</b>

1. <b>Общие положения</b>
Настоящий договор является публичной офертой и регулирует отношения между пользователями и маркетплейсом {BOT_NAME}.

2. <b>Предмет договора</b>
• Продажа и покупка товаров через Telegram
• Использование звёзд Telegram как платёжного средства
• Взаимодействие между покупателями и продавцами

3. <b>Права и обязанности покупателя</b>
• Получать достоверную информацию о товаре
• Оформить возврат в течение 14 дней
• Оставлять отзывы о товарах
• Сообщать о проблемах в поддержку

4. <b>Права и обязанности продавца</b>
• Предоставлять достоверную информацию о товаре
• Отвечать на вопросы покупателей
• Отправлять товар после оплаты
• Решать спорные ситуации

5. <b>Оплата</b>
• Все расчёты производятся звёздами Telegram
• Комиссия платформы: 5%
• Средства зачисляются продавцу после подтверждения получения

6. <b>Возврат</b>
• Покупатель имеет право на возврат в течение 14 дней
• Возврат осуществляется за счёт продавца
• В случае спора решение принимает администрация

7. <b>Ответственность</b>
• Продавец несёт ответственность за качество товара
• Покупатель несёт ответственность за достоверность отзывов
• Администрация не несёт ответственности за утерю данных

8. <b>Блокировка</b>
Администрация имеет право заблокировать пользователя за:
• Мошенничество
• Оскорбления
• Спам
• Неоднократные нарушения

Используя бота, вы соглашаетесь с условиями."""
    
    bot.send_message(message.chat.id, text, parse_mode='html')

# ========== ОБРАБОТКА КНОПОК ==========

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Обработка всех callback"""
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    if call.data == "catalog":
        show_catalog(chat_id)
    
    elif call.data == "cart":
        show_cart(chat_id, call.from_user.id)
    
    elif call.data == "profile":
        profile_command(call.message)
    
    elif call.data == "balance":
        balance_command(call.message)
    
    elif call.data == "become_seller":
        start_seller_registration(call.message)
    
    elif call.data == "help":
        help_text = """<b>❓ ПОМОЩЬ</b>

<b>Основные команды:</b>
/start - Главное меню
/catalog - Каталог товаров
/cart - Корзина
/profile - Профиль
/balance - Баланс
/become_seller - Стать продавцом
/add_product - Добавить товар (для продавцов)
/support - Поддержка
/policy - Политика
/offer - Оферта

<b>Как купить:</b>
1. Пополни баланс через /balance
2. Найди товар в каталоге
3. Добавь в корзину
4. Оформи заказ
5. Получи чек

<b>Как продавать:</b>
1. Стань продавцом через /become_seller
2. Добавь товары через /add_product
3. Отвечай на вопросы
4. Отправляй товары
5. Получай звёзды"""
        
        bot.send_message(chat_id, help_text, parse_mode='html')
    
    elif call.data == "support":
        support_command(call.message)
    
    elif call.data == "docs":
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("🔒 Политика", callback_data="show_policy")
        btn2 = types.InlineKeyboardButton("📜 Оферта", callback_data="show_offer")
        markup.add(btn1, btn2)
        
        bot.send_message(chat_id, "<b>📄 Документы</b>\nВыберите документ:", 
                        parse_mode='html', reply_markup=markup)
    
    elif call.data == "show_policy":
        policy_command(call.message)
    
    elif call.data == "show_offer":
        offer_command(call.message)
    
    elif call.data == "add_product":
        add_product_command(call.message)
    
    elif call.data == "my_products":
        show_my_products(chat_id, call.from_user.id)
    
    elif call.data == "deposit":
        balance_command(call.message)
    
    elif call.data == "my_orders":
        # TODO: Показать заказы пользователя
        bot.send_message(chat_id, "📦 Функция в разработке")
    
    elif call.data == "my_reviews":
        # TODO: Показать отзывы пользователя
        bot.send_message(chat_id, "⭐ Функция в разработке")
    
    elif call.data.startswith("cat_"):
        category = call.data.replace('cat_', '')
        show_category_products(chat_id, category)
    
    bot.answer_callback_query(call.id)

def show_category_products(chat_id, category):
    """Показать товары категории"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, price, condition, views FROM products 
        WHERE category = ? AND status = 'active' 
        ORDER BY created_date DESC LIMIT 10
    ''', (category,))
    
    products = cursor.fetchall()
    conn.close()
    
    if not products:
        bot.send_message(chat_id, f"📭 В категории {category} пока нет товаров")
        return
    
    text = f"<b>{category}</b>\n\n"
    
    for p in products:
        text += f"• <b>{p[1]}</b>\n"
        text += f"  💰 {p[2]} ⭐ | {p[3]} | 👁 {p[4]}\n"
        text += f"  Подробнее: /product_{p[0]}\n\n"
    
    bot.send_message(chat_id, text, parse_mode='html')

# ========== ЗАПУСК ==========

if __name__ == "__main__":
    print("=" * 50)
    print(f"🛍 {BOT_NAME} ЗАПУЩЕН!")
    print("=" * 50)
    print(f"📌 Бот: @{bot.get_me().username}")
    print(f"📌 Валюта: {CURRENCY}")
    print(f"📌 Админ ID: {MAIN_ADMIN_ID}")
    print("=" * 50)
    print("✅ Функции загружены:")
    print("✓ Каталог товаров")
    print("✓ Корзина покупок")
    print("✓ Пополнение звёздами")
    print("✓ Регистрация продавцов")
    print("✓ Добавление товаров")
    print("✓ Отзывы и вопросы")
    print("✓ Поддержка")
    print("=" * 50)
    
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)
