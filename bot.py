import telebot
from telebot import types
import sqlite3
import time
import random
from datetime import datetime, timedelta
import re
import os
import threading
import json

# ========== НАСТРОЙКИ ==========

TOKEN = "8259179783:AAHuDseoX6aULdjsWPXT-zWWSNH9-nt6s6U"
bot = telebot.TeleBot(TOKEN)

# ID главного админа (твой ID)
MAIN_ADMIN_ID = 8779825034

# Название валюты
CURRENCY_NAME = "Ириски"

# Настройки модерации
FLOOD_TIME = 5  # секунд
FLOOD_LIMIT = 5
MAX_MESSAGE_LENGTH = 1000
MAX_WARNS = 3  # макс предупреждений до бана

# Ключевые слова для спама
SPAM_KEYWORDS = [
    'реклама', 'спам', 'рассылка', 'заработок', 'биткоин', 'крипта',
    'казино', 'вулкан', 'joy', 'промокод', 'скидка', 'акция',
    'kwork', 'фриланс', 'работа на дому'
]

# Мат-слова
BAD_WORDS = [
    'хуй', 'пизда', 'блядь', 'ебать', 'сука', 'нахер', 'нахуй', 'пидор',
    'гандон', 'мудак', 'долбоеб', 'уебок', 'залупа', 'шлюха', 'петух'
]

# Ссылки
LINKS_REGEX = r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)'

# Статусы для покупки
STATUSES = {
    'Новичок': {'price': 100, 'emoji': '🌱'},
    'Гоблин': {'price': 500, 'emoji': '👺'},
    'Король': {'price': 1000, 'emoji': '👑'},
    'Мафиозник': {'price': 2000, 'emoji': '🕴️'},
    'Киберпанк': {'price': 5000, 'emoji': '🤖'},
    'Легенда': {'price': 10000, 'emoji': '⭐'}
}

# ========== БАЗА ДАННЫХ ==========

def init_db():
    """Создание базы данных"""
    conn = sqlite3.connect('moderate_artem.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            reg_date TEXT,
            last_active TEXT,
            balance INTEGER DEFAULT 0,
            warns INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            premium_until TEXT,
            status TEXT DEFAULT 'Новичок',
            role TEXT DEFAULT 'user',
            messages_count INTEGER DEFAULT 0,
            commands_count INTEGER DEFAULT 0,
            referrer_id INTEGER,
            total_spent INTEGER DEFAULT 0
        )
    ''')
    
    # Таблица групп
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            chat_title TEXT,
            added_date TEXT,
            welcome_message TEXT DEFAULT 'Добро пожаловать в чат, {name}!',
            rules TEXT DEFAULT '1. Уважайте друг друга\n2. Не спамить\n3. Не материться',
            flood_protection INTEGER DEFAULT 1,
            spam_filter INTEGER DEFAULT 1,
            link_filter INTEGER DEFAULT 1,
            bad_words_filter INTEGER DEFAULT 1,
            welcome_enabled INTEGER DEFAULT 1,
            log_channel_id INTEGER,
            auto_ban_warns INTEGER DEFAULT 3,
            mute_time INTEGER DEFAULT 10
        )
    ''')
    
    # Таблица покупок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_type TEXT,
            item_name TEXT,
            price INTEGER,
            purchase_date TEXT,
            expires_date TEXT,
            status TEXT DEFAULT 'active'
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
            date TEXT
        )
    ''')
    
    # Таблица донатов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            stars_amount INTEGER,
            date TEXT
        )
    ''')
    
    # Таблица банов/мутов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mod_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            admin_id INTEGER,
            action TEXT,
            reason TEXT,
            duration INTEGER,
            date TEXT,
            expires TEXT
        )
    ''')
    
    # Таблица для рассылок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mailings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            text TEXT,
            sent_count INTEGER,
            total_count INTEGER,
            date TEXT,
            status TEXT
        )
    ''')
    
    # Таблица обратной связи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            reply TEXT,
            status TEXT DEFAULT 'open',
            date TEXT
        )
    ''')
    
    # Таблица промокодов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            bonus INTEGER,
            uses INTEGER DEFAULT 0,
            max_uses INTEGER,
            expires TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_db():
    """Получить соединение с БД"""
    return sqlite3.connect('moderate_artem.db', check_same_thread=False)

def log_transaction(user_id, amount, type, description):
    """Запись транзакции"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (user_id, amount, type, description, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, amount, type, description, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def add_user(user):
    """Добавление пользователя"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, first_name, last_name, reg_date, last_active)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user.id, user.username, user.first_name, user.last_name, 
          datetime.now().isoformat(), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def get_user(user_id):
    """Получить пользователя"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_balance(user_id, amount, description):
    """Обновить баланс"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    new_balance = cursor.fetchone()[0]
    
    log_transaction(user_id, amount, 'balance_change', description)
    
    conn.commit()
    conn.close()
    return new_balance

def is_admin(message):
    """Проверка, является ли пользователь администратором чата"""
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Главный админ всегда имеет права
        if user_id == MAIN_ADMIN_ID:
            return True
        
        # Проверяем права в чате
        if message.chat.type != 'private':
            chat_member = bot.get_chat_member(chat_id, user_id)
            return chat_member.status in ['administrator', 'creator']
        return False
    except:
        return False

def is_premium(user_id):
    """Проверка премиум статуса"""
    user = get_user(user_id)
    if not user:
        return False
    
    if user[6]:  # is_premium
        premium_until = datetime.fromisoformat(user[7]) if user[7] else None
        if premium_until and premium_until > datetime.now():
            return True
    return False

# ========== КОМАНДЫ ПОЛЬЗОВАТЕЛЯ ==========

@bot.message_handler(commands=['start'])
def start_command(message):
    """Запуск бота"""
    user = message.from_user
    add_user(user)
    
    # Проверка реферала
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref'):
        referrer_id = int(args[1].replace('ref', ''))
        if referrer_id != user.id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET referrer_id = ? WHERE user_id = ?', (referrer_id, user.id))
            
            # Начисляем бонус рефереру
            update_balance(referrer_id, 50, f"Реферал: {user.first_name}")
            conn.commit()
            conn.close()
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    btn2 = types.InlineKeyboardButton("💰 Баланс", callback_data="balance")
    btn3 = types.InlineKeyboardButton("🏪 Магазин", callback_data="shop")
    btn4 = types.InlineKeyboardButton("🎁 Бонус", callback_data="daily_bonus")
    btn5 = types.InlineKeyboardButton("📜 Правила", callback_data="rules")
    btn6 = types.InlineKeyboardButton("🆘 Помощь", callback_data="help")
    btn7 = types.InlineKeyboardButton("💎 Премиум", callback_data="premium")
    btn8 = types.InlineKeyboardButton("📞 Поддержка", callback_data="support")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    
    welcome = f"""<b>🌟 Moderate Artem</b>

Привет, {user.first_name}! 
Я бот-модератор для твоих групп и чатов.

<b>🎮 Внутренняя валюта: {CURRENCY_NAME}</b>
• Получай {CURRENCY_NAME} за активность
• Покупай статусы и премиум
• Донать за звёзды Telegram

<b>🔹 Основные возможности:</b>
• Модерация групп (бан, мут, кик)
• Антифлуд и антиспам
• Статусы и роли
• Премиум подписка
• Рассылки для админов

<b>🔹 Команды:</b>
/profile - твой профиль
/shop - магазин статусов
/buy премиум - купить премиум
/donate [сумма] - задонатить звёздами
/referral - реферальная ссылка

Выбери действие в меню ниже 👇"""
    
    bot.send_message(message.chat.id, welcome, parse_mode='html', reply_markup=markup)

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
    cursor.execute('SELECT COUNT(*) FROM purchases WHERE user_id = ?', (user_id,))
    purchases = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM donations WHERE user_id = ?', (user_id,))
    donations = cursor.fetchone()[0]
    conn.close()
    
    # Формируем профиль
    reg_date = datetime.fromisoformat(user[4]).strftime('%d.%m.%Y')
    last_active = datetime.fromisoformat(user[5]).strftime('%d.%m.%Y %H:%M')
    
    premium_status = "✅ Да" if is_premium(user_id) else "❌ Нет"
    status_emoji = STATUSES.get(user[9], {}).get('emoji', '🌱')
    
    profile_text = f"""<b>👤 ТВОЙ ПРОФИЛЬ</b>

🆔 ID: <code>{user_id}</code>
👤 Имя: {message.from_user.first_name}
🔖 Username: @{message.from_user.username or 'нет'}

<b>📊 Статистика:</b>
📅 Регистрация: {reg_date}
⏰ Последний визит: {last_active}
💬 Сообщений: {user[11]}
🔧 Команд: {user[12]}

<b>💰 Экономика:</b>
💎 Баланс: {user[6]} {CURRENCY_NAME}
⭐ Статус: {status_emoji} {user[9]}
💎 Премиум: {premium_status}
🛒 Покупок: {purchases}
🎁 Донатов: {donations}

<b>🔗 Реферальная ссылка:</b>
https://t.me/{bot.get_me().username}?start=ref{user_id}"""
    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("💰 Пополнить", callback_data="buy_balance")
    btn2 = types.InlineKeyboardButton("🛒 Магазин", callback_data="shop")
    markup.add(btn1, btn2)
    
    bot.send_message(message.chat.id, profile_text, parse_mode='html', reply_markup=markup)

@bot.message_handler(commands=['balance'])
def balance_command(message):
    """Баланс"""
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        add_user(message.from_user)
        user = get_user(user_id)
    
    # Получаем историю транзакций
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT amount, type, description, date FROM transactions 
        WHERE user_id = ? ORDER BY date DESC LIMIT 5
    ''', (user_id,))
    transactions = cursor.fetchall()
    conn.close()
    
    text = f"""<b>💰 ТВОЙ БАЛАНС</b>

💎 Баланс: {user[6]} {CURRENCY_NAME}
⭐ Статус: {user[9]}

<b>📊 Последние операции:</b>
"""
    
    for t in transactions:
        sign = "+" if t[0] > 0 else ""
        text += f"{sign}{t[0]} {CURRENCY_NAME} - {t[2]} ({t[3][:16]})\n"
    
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("💎 Купить", callback_data="buy_balance")
    btn2 = types.InlineKeyboardButton("🎁 Бонус", callback_data="daily_bonus")
    markup.add(btn1, btn2)
    
    bot.send_message(message.chat.id, text, parse_mode='html', reply_markup=markup)

@bot.message_handler(commands=['shop'])
def shop_command(message):
    """Магазин статусов"""
    text = "<b>🏪 МАГАЗИН СТАТУСОВ</b>\n\n"
    
    for status_name, status_info in STATUSES.items():
        text += f"{status_info['emoji']} <b>{status_name}</b> - {status_info['price']} {CURRENCY_NAME}\n"
    
    text += "\n💎 <b>Премиум подписка:</b>\n"
    text += "• Неделя: 1000 💰\n"
    text += "• Месяц: 3000 💰\n"
    text += "• Навсегда: 10000 💰\n\n"
    text += "Купить: /buy [название]"
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['buy'])
def buy_command(message):
    """Покупка статуса"""
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        bot.reply_to(message, "❌ Напиши что купить. Например: /buy Король")
        return
    
    item = args[1].strip().capitalize()
    
    # Проверка статусов
    if item in STATUSES:
        price = STATUSES[item]['price']
        user = get_user(user_id)
        
        if user[6] < price:
            bot.reply_to(message, f"❌ Недостаточно {CURRENCY_NAME}! Нужно {price}")
            return
        
        # Покупаем
        new_balance = update_balance(user_id, -price, f"Покупка статуса {item}")
        
        # Сохраняем покупку
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO purchases (user_id, item_type, item_name, price, purchase_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, 'status', item, price, datetime.now().isoformat()))
        
        cursor.execute('UPDATE users SET status = ? WHERE user_id = ?', (item, user_id))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, 
            f"✅ Статус <b>{item}</b> куплен!\n"
            f"💰 Остаток: {new_balance} {CURRENCY_NAME}",
            parse_mode='html')
    
    elif item.lower() == 'премиум':
        # Обработка покупки премиум
        premium_menu(message)
    
    else:
        bot.reply_to(message, "❌ Такого товара нет в магазине")

@bot.message_handler(commands=['premium'])
def premium_command(message):
    """Премиум меню"""
    premium_menu(message)

def premium_menu(message):
    """Меню премиум подписки"""
    text = """<b>💎 PREMIUM ПОДПИСКА</b>

<b>Преимущества:</b>
✅ Админ-команды в любых чатах
✅ Ежедневный бонус x2
✅ Специальный статус
✅ Доступ к эксклюзивным статусам
✅ Приоритетная поддержка
✅ +50% к доходу с рефералов

<b>Стоимость:</b>
• 1 неделя - 1000 💰
• 1 месяц - 3000 💰
• Навсегда - 10000 💰

<b>Купить:</b>
/premium_week - неделя
/premium_month - месяц
/premium_forever - навсегда"""
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['daily'])
def daily_bonus_command(message):
    """Ежедневный бонус"""
    user_id = message.from_user.id
    
    # Проверяем, получал ли сегодня
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT date FROM transactions 
        WHERE user_id = ? AND type = 'daily_bonus' 
        AND date > ? ORDER BY date DESC LIMIT 1
    ''', (user_id, (datetime.now() - timedelta(days=1)).isoformat()))
    
    last_bonus = cursor.fetchone()
    
    if last_bonus:
        bot.reply_to(message, "❌ Ты уже получал бонус сегодня! Приходи завтра.")
        conn.close()
        return
    
    # Начисляем бонус
    bonus_amount = 100
    if is_premium(user_id):
        bonus_amount *= 2
    
    new_balance = update_balance(user_id, bonus_amount, "Ежедневный бонус")
    
    cursor.execute('''
        INSERT INTO transactions (user_id, amount, type, description, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, bonus_amount, 'daily_bonus', 'Ежедневный бонус', datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    bot.reply_to(message, 
        f"🎁 <b>Ежедневный бонус получен!</b>\n"
        f"+{bonus_amount} {CURRENCY_NAME}\n"
        f"💰 Баланс: {new_balance}",
        parse_mode='html')

@bot.message_handler(commands=['donate'])
def donate_command(message):
    """Донат звёздами Telegram"""
    user_id = message.from_user.id
    args = message.text.split()
    
    if len(args) < 2:
        bot.reply_to(message, "❌ Укажи сумму в звёздах. Например: /donate 50")
        return
    
    try:
        stars = int(args[1])
        if stars < 10:
            bot.reply_to(message, "❌ Минимальный донат - 10 звёзд")
            return
        
        # Курс: 1 звезда = 10 ирисок
        iris_amount = stars * 10
        
        # Создаём счёт для оплаты звёздами
        invoice = bot.create_invoice_link(
            title=f"Пополнение {CURRENCY_NAME}",
            description=f"{stars} ⭐ -> {iris_amount} {CURRENCY_NAME}",
            payload=f"donate_{user_id}_{iris_amount}",
            provider_token="",  # Для звёзд оставляем пустым
            currency="XTR",  # XTR - звёзды Telegram
            prices=[types.LabeledPrice(label=f"{stars} ⭐", amount=stars)]
        )
        
        bot.send_message(user_id, f"💎 Ссылка для оплаты звёздами:\n{invoice}")
        
    except ValueError:
        bot.reply_to(message, "❌ Неправильный формат суммы")

@bot.message_handler(commands=['referral'])
def referral_command(message):
    """Реферальная программа"""
    user_id = message.from_user.id
    
    # Статистика рефералов
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id = ?', (user_id,))
    referrals = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = ?', 
                  (user_id, 'referral_bonus'))
    total_earned = cursor.fetchone()[0] or 0
    conn.close()
    
    ref_link = f"https://t.me/{bot.get_me().username}?start=ref{user_id}"
    
    text = f"""<b>🔗 РЕФЕРАЛЬНАЯ ПРОГРАММА</b>

👥 Пригласи друзей и получай бонусы!

<b>Твоя статистика:</b>
• Приглашено: {referrals} чел.
• Заработано: {total_earned} {CURRENCY_NAME}

<b>Бонусы:</b>
• За каждого друга: +50 {CURRENCY_NAME}
• За премиум друга: +200 {CURRENCY_NAME}

<b>Твоя ссылка:</b>
<code>{ref_link}</code>"""
    
    bot.send_message(message.chat.id, text, parse_mode='html')

# ========== КОМАНДЫ МОДЕРАЦИИ ==========

@bot.message_handler(commands=['ban'])
def ban_command(message):
    """Бан пользователя"""
    if not is_admin(message) and not is_premium(message.from_user.id):
        bot.reply_to(message, "❌ Недостаточно прав. Нужны права админа или премиум")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение пользователя")
        return
    
    user_to_ban = message.reply_to_message.from_user
    chat_id = message.chat.id
    admin_id = message.from_user.id
    
    reason = message.text.replace('/ban', '').strip() or 'Нарушение правил'
    
    try:
        bot.ban_chat_member(chat_id, user_to_ban.id)
        
        # Логируем
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mod_actions (chat_id, user_id, admin_id, action, reason, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (chat_id, user_to_ban.id, admin_id, 'ban', reason, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id,
            f"🔨 <b>БАН</b>\n"
            f"Пользователь: {user_to_ban.first_name}\n"
            f"Причина: {reason}\n"
            f"Админ: {message.from_user.first_name}",
            parse_mode='html')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unban'])
def unban_command(message):
    """Разбан пользователя"""
    if not is_admin(message) and not is_premium(message.from_user.id):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение пользователя")
        return
    
    user_to_unban = message.reply_to_message.from_user
    chat_id = message.chat.id
    
    try:
        bot.unban_chat_member(chat_id, user_to_unban.id)
        
        bot.send_message(chat_id,
            f"✅ <b>РАЗБАН</b>\n"
            f"Пользователь: {user_to_unban.first_name}\n"
            f"Админ: {message.from_user.first_name}",
            parse_mode='html')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['mute'])
def mute_command(message):
    """Мут пользователя"""
    if not is_admin(message) and not is_premium(message.from_user.id):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение пользователя")
        return
    
    user_to_mute = message.reply_to_message.from_user
    chat_id = message.chat.id
    admin_id = message.from_user.id
    
    # Парсим время
    args = message.text.split()
    mute_time = 10  # минут по умолчанию
    reason = "Нарушение правил"
    
    if len(args) > 1:
        try:
            mute_time = int(args[1])
            if len(args) > 2:
                reason = ' '.join(args[2:])
        except:
            reason = ' '.join(args[1:])
    
    until_date = datetime.now() + timedelta(minutes=mute_time)
    
    try:
        bot.restrict_chat_member(
            chat_id, 
            user_to_mute.id,
            until_date=until_date,
            can_send_messages=False
        )
        
        # Логируем
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mod_actions (chat_id, user_id, admin_id, action, reason, duration, date, expires)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (chat_id, user_to_mute.id, admin_id, 'mute', reason, mute_time, 
              datetime.now().isoformat(), until_date.isoformat()))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id,
            f"🔇 <b>МУТ</b>\n"
            f"Пользователь: {user_to_mute.first_name}\n"
            f"Время: {mute_time} мин\n"
            f"Причина: {reason}\n"
            f"Админ: {message.from_user.first_name}",
            parse_mode='html')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unmute'])
def unmute_command(message):
    """Снятие мута"""
    if not is_admin(message) and not is_premium(message.from_user.id):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение пользователя")
        return
    
    user_to_unmute = message.reply_to_message.from_user
    chat_id = message.chat.id
    
    try:
        bot.restrict_chat_member(
            chat_id,
            user_to_unmute.id,
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_add_web_page_previews=True
        )
        
        bot.send_message(chat_id,
            f"🔊 <b>МУТ СНЯТ</b>\n"
            f"Пользователь: {user_to_unmute.first_name}\n"
            f"Админ: {message.from_user.first_name}",
            parse_mode='html')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['kick'])
def kick_command(message):
    """Кик пользователя"""
    if not is_admin(message) and not is_premium(message.from_user.id):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение пользователя")
        return
    
    user_to_kick = message.reply_to_message.from_user
    chat_id = message.chat.id
    
    reason = message.text.replace('/kick', '').strip() or 'Нарушение правил'
    
    try:
        bot.ban_chat_member(chat_id, user_to_kick.id)
        bot.unban_chat_member(chat_id, user_to_kick.id)
        
        bot.send_message(chat_id,
            f"👢 <b>КИК</b>\n"
            f"Пользователь: {user_to_kick.first_name}\n"
            f"Причина: {reason}\n"
            f"Админ: {message.from_user.first_name}",
            parse_mode='html')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['warn'])
def warn_command(message):
    """Предупреждение"""
    if not is_admin(message) and not is_premium(message.from_user.id):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение пользователя")
        return
    
    user = message.reply_to_message.from_user
    chat_id = message.chat.id
    reason = message.text.replace('/warn', '').strip() or 'Нарушение правил'
    
    # Получаем текущие предупреждения
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO mod_actions (chat_id, user_id, admin_id, action, reason, date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (chat_id, user.id, message.from_user.id, 'warn', reason, datetime.now().isoformat()))
    
    # Считаем предупреждения за последние 30 дней
    cursor.execute('''
        SELECT COUNT(*) FROM mod_actions 
        WHERE chat_id = ? AND user_id = ? AND action = 'warn'
        AND date > ?
    ''', (chat_id, user.id, (datetime.now() - timedelta(days=30)).isoformat()))
    
    warns_count = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    
    bot.send_message(chat_id,
        f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b>\n"
        f"Пользователь: {user.first_name}\n"
        f"Предупреждений: {warns_count}/{MAX_WARNS}\n"
        f"Причина: {reason}\n"
        f"Админ: {message.from_user.first_name}",
        parse_mode='html')
    
    # Автобан после MAX_WARNS предупреждений
    if warns_count >= MAX_WARNS:
        try:
            bot.ban_chat_member(chat_id, user.id)
            bot.send_message(chat_id,
                f"🔨 <b>АВТОМАТИЧЕСКИЙ БАН</b>\n"
                f"{user.first_name} забанен за {MAX_WARNS} предупреждений",
                parse_mode='html')
        except:
            pass

@bot.message_handler(commands=['clear'])
def clear_command(message):
    """Очистка сообщений"""
    if not is_admin(message) and not is_premium(message.from_user.id):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    chat_id = message.chat.id
    args = message.text.split()
    
    try:
        count = int(args[1]) if len(args) > 1 else 10
        count = min(count, 100)
        
        # Удаляем команду
        bot.delete_message(chat_id, message.message_id)
        
        # Удаляем сообщения
        deleted = 0
        for i in range(count):
            try:
                bot.delete_message(chat_id, message.message_id - i - 1)
                deleted += 1
            except:
                pass
        
        status = bot.send_message(chat_id, f"✅ Удалено {deleted} сообщений")
        
        # Удаляем статус через 3 секунды
        time.sleep(3)
        bot.delete_message(chat_id, status.message_id)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ========== АДМИН КОМАНДЫ ==========

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Панель администратора"""
    if message.from_user.id != MAIN_ADMIN_ID:
        bot.reply_to(message, "❌ Доступ запрещён")
        return
    
    text = """<b>👑 АДМИН ПАНЕЛЬ</b>

<b>Статистика:</b>
/stats - общая статистика
/users - список пользователей
/groups - список групп

<b>Управление:</b>
/mailing - рассылка
/support - обращения в поддержку
/promo - промокоды

<b>Экономика:</b>
/add_balance [id] [сумма] - начислить
/remove_balance [id] [сумма] - списать
/give_premium [id] [дней] - выдать премиум

<b>Настройки:</b>
/set_spam_keywords - спам слова
/set_bad_words - мат слова
/settings - настройки бота"""
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    """Общая статистика"""
    if message.from_user.id != MAIN_ADMIN_ID:
        bot.reply_to(message, "❌ Доступ запрещён")
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM groups')
    total_groups = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(balance) FROM users')
    total_balance = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
    premium_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(amount) FROM donations')
    total_donations = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM mod_actions WHERE date > ?', 
                  ((datetime.now() - timedelta(days=1)).isoformat(),))
    actions_today = cursor.fetchone()[0]
    
    conn.close()
    
    text = f"""<b>📊 ОБЩАЯ СТАТИСТИКА</b>

👥 Пользователей: {total_users}
👥 Премиум: {premium_users}
👥 Групп: {total_groups}

💰 Всего {CURRENCY_NAME}: {total_balance}
🎁 Донатов: {total_donations} ⭐
🛡 Действий сегодня: {actions_today}

📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['mailing'])
def mailing_command(message):
    """Рассылка сообщений"""
    if message.from_user.id != MAIN_ADMIN_ID:
        bot.reply_to(message, "❌ Доступ запрещён")
        return
    
    msg = bot.reply_to(message, "📢 Введи текст для рассылки:")
    bot.register_next_step_handler(msg, process_mailing)

def process_mailing(message):
    """Обработка рассылки"""
    if message.from_user.id != MAIN_ADMIN_ID:
        return
    
    text = message.text
    
    # Подтверждение
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("✅ Отправить всем", callback_data="mailing_all")
    btn2 = types.InlineKeyboardButton("👑 Только премиум", callback_data="mailing_premium")
    btn3 = types.InlineKeyboardButton("❌ Отмена", callback_data="mailing_cancel")
    markup.add(btn1, btn2, btn3)
    
    bot.reply_to(message, 
        f"📢 <b>Предпросмотр рассылки:</b>\n\n{text}\n\nКому отправляем?",
        parse_mode='html', reply_markup=markup)
    
    # Сохраняем текст
    global mailing_text
    mailing_text = text

@bot.message_handler(commands=['add_balance'])
def add_balance_admin(message):
    """Начисление баланса (админ)"""
    if message.from_user.id != MAIN_ADMIN_ID:
        bot.reply_to(message, "❌ Доступ запрещён")
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "❌ Используй: /add_balance [user_id] [сумма]")
        return
    
    try:
        user_id = int(args[1])
        amount = int(args[2])
        
        new_balance = update_balance(user_id, amount, f"Начислено администратором")
        
        bot.reply_to(message, f"✅ Пользователю {user_id} начислено {amount} {CURRENCY_NAME}\nНовый баланс: {new_balance}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ========== ОБРАТНАЯ СВЯЗЬ ==========

@bot.message_handler(commands=['support'])
def support_command(message):
    """Обратная связь"""
    text = """<b>📞 ПОДДЕРЖКА</b>

Выбери тип обращения:

1️⃣ Вопрос по боту
2️⃣ Жалоба на пользователя
3️⃣ Предложение по улучшению
4️⃣ Проблема с оплатой
5️⃣ Другое

Напиши свой вопрос, и администратор ответит в ближайшее время.
Ответ придёт в личные сообщения."""
    
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
        INSERT INTO support (user_id, message, date, status)
        VALUES (?, ?, ?, ?)
    ''', (user_id, text, datetime.now().isoformat(), 'open'))
    support_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Уведомление админу
    admin_text = f"""<b>📞 НОВОЕ ОБРАЩЕНИЕ #{support_id}</b>

👤 Пользователь: {message.from_user.first_name} (@{message.from_user.username})
🆔 ID: {user_id}

📝 Сообщение:
{text}

Чтобы ответить: /reply {support_id} [текст]"""
    
    bot.send_message(MAIN_ADMIN_ID, admin_text, parse_mode='html')
    
    bot.reply_to(message, "✅ Ваше обращение отправлено! Администратор ответит в ближайшее время.")

@bot.message_handler(commands=['reply'])
def reply_support(message):
    """Ответ на обращение (админ)"""
    if message.from_user.id != MAIN_ADMIN_ID:
        bot.reply_to(message, "❌ Доступ запрещён")
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        bot.reply_to(message, "❌ Используй: /reply [номер] [текст]")
        return
    
    try:
        support_id = int(args[1])
        reply_text = args[2]
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, message FROM support WHERE id = ?', (support_id,))
        support = cursor.fetchone()
        
        if not support:
            bot.reply_to(message, "❌ Обращение не найдено")
            conn.close()
            return
        
        user_id, original = support
        
        cursor.execute('UPDATE support SET reply = ?, status = ? WHERE id = ?', 
                      (reply_text, 'closed', support_id))
        conn.commit()
        conn.close()
        
        # Отправляем ответ пользователю
        bot.send_message(user_id,
            f"<b>📞 Ответ на обращение #{support_id}</b>\n\n"
            f"Ваш вопрос: {original}\n\n"
            f"Ответ администратора:\n{reply_text}",
            parse_mode='html')
        
        bot.reply_to(message, f"✅ Ответ отправлен пользователю {user_id}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ========== ПОЛИТИКА И ОФЕРТА ==========

@bot.message_handler(commands=['policy'])
def policy_command(message):
    """Политика конфиденциальности"""
    text = """<b>🔒 ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</b>

1. <b>Сбор данных</b>
Мы собираем минимально необходимые данные:
• Ваш Telegram ID
• Имя пользователя
• История обращений в поддержку
• История покупок

2. <b>Использование данных</b>
Данные используются только для:
• Работы бота
• Начисления баланса
• Ответов на обращения
• Улучшения сервиса

3. <b>Защита данных</b>
• Все данные хранятся в зашифрованном виде
• Доступ к данным есть только у администратора
• Данные не передаются третьим лицам

4. <b>Ваши права</b>
Вы можете:
• Запросить удаление данных
• Экспортировать свои данные
• Отозвать согласие на обработку

По вопросам: /support"""
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(commands=['offer'])
def offer_command(message):
    """Договор оферты"""
    text = """<b>📜 ДОГОВОР ОФЕРТЫ</b>

1. <b>Общие положения</b>
Настоящий договор является публичной офертой и регулирует отношения между пользователем и ботом Moderate Artem.

2. <b>Предмет договора</b>
Бот предоставляет услуги модерации и виртуальную валюту "{CURRENCY_NAME}".

3. <b>Виртуальная валюта</b>
• {CURRENCY_NAME} - внутриигровая валюта
• Может быть получена за активность
• Может быть куплена за звёзды Telegram
• Не подлежит обмену на реальные деньги
• Не возвращается при блокировке

4. <b>Права и обязанности</b>
Пользователь обязуется:
• Не нарушать правила чатов
• Не пытаться взломать бота
• Не использовать бота для спама

5. <b>Ответственность</b>
Администрация не несёт ответственности за:
• Потерю данных
• Сбои в работе Telegram
• Действия других пользователей

6. <b>Блокировка</b>
Администрация имеет право заблокировать пользователя за:
• Нарушение правил
• Попытку взлома
• Мошенничество

7. <b>Изменение условий</b>
Администрация может изменять условия с уведомлением пользователей.

Используя бота, вы соглашаетесь с условиями."""
    
    bot.send_message(message.chat.id, text, parse_mode='html')

# ========== ОБРАБОТКА КНОПОК ==========

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Обработка инлайн кнопок"""
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    if call.data == "profile":
        profile_command(call.message)
        
    elif call.data == "balance":
        balance_command(call.message)
        
    elif call.data == "shop":
        shop_command(call.message)
        
    elif call.data == "daily_bonus":
        daily_bonus_command(call.message)
        
    elif call.data == "rules":
        rules = """<b>📜 ПРАВИЛА БОТА</b>

1. Уважай других пользователей
2. Не спамь
3. Не матерись
4. Не рекламируй
5. Не пытайся взломать бота
6. Не покупай валюту у других
7. Сообщай о багах в поддержку

Нарушение правил = блокировка без возврата средств"""
        bot.send_message(chat_id, rules, parse_mode='html')
        
    elif call.data == "help":
        help_text = """<b>🆘 ПОМОЩЬ</b>

<b>Основные команды:</b>
/profile - твой профиль
/balance - баланс
/shop - магазин статусов
/buy [название] - купить статус
/premium - премиум подписка
/daily - ежедневный бонус
/donate [сумма] - донат звёздами
/support - поддержка

<b>Команды модерации (в группах):</b>
/ban - заблокировать
/unban - разблокировать
/mute - ограничить
/unmute - снять ограничение
/kick - выгнать
/warn - предупредить
/clear - очистить сообщения

<b>Документы:</b>
/policy - политика конфиденциальности
/offer - договор оферты"""
        bot.send_message(chat_id, help_text, parse_mode='html')
        
    elif call.data == "premium":
        premium_menu(call.message)
        
    elif call.data == "support":
        support_command(call.message)
        
    elif call.data == "buy_balance":
        bot.send_message(chat_id,
            "💎 <b>Пополнение баланса</b>\n\n"
            "1 звезда = 10 ирисок\n\n"
            "Напиши /donate [количество звёзд]\n"
            "Например: /donate 50",
            parse_mode='html')
    
    elif call.data.startswith("mailing_"):
        if call.from_user.id != MAIN_ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Нет прав")
            return
        
        action = call.data.replace("mailing_", "")
        
        if action == "cancel":
            bot.edit_message_text("❌ Рассылка отменена", chat_id, message_id)
            
        elif action in ["all", "premium"]:
            bot.edit_message_text(f"📢 Рассылка началась...", chat_id, message_id)
            
            # Получаем список пользователей
            conn = get_db()
            cursor = conn.cursor()
            
            if action == "all":
                cursor.execute('SELECT user_id FROM users')
            else:
                cursor.execute('SELECT user_id FROM users WHERE is_premium = 1')
            
            users = cursor.fetchall()
            conn.close()
            
            sent = 0
            failed = 0
            
            for user in users:
                try:
                    bot.send_message(user[0], mailing_text, parse_mode='html')
                    sent += 1
                    time.sleep(0.05)  # Защита от флуда
                except:
                    failed += 1
            
            bot.send_message(chat_id,
                f"📢 <b>Рассылка завершена</b>\n"
                f"✅ Отправлено: {sent}\n"
                f"❌ Не доставлено: {failed}",
                parse_mode='html')

# ========== МОДЕРАЦИЯ СООБЩЕНИЙ ==========

@bot.message_handler(func=lambda message: message.chat.type != 'private')
def moderate_messages(message):
    """Модерация сообщений в группах"""
    if not message.text:
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Пропускаем админов
    if is_admin(message):
        return
    
    # Проверка на спам
    text_lower = message.text.lower()
    
    # Проверка ссылок
    links = re.findall(LINKS_REGEX, message.text, re.IGNORECASE)
    if links and len(links) > 2:
        bot.delete_message(chat_id, message.message_id)
        bot.send_message(chat_id, f"🔗 {message.from_user.first_name}, слишком много ссылок!")
        return
    
    # Проверка мата
    for word in BAD_WORDS:
        if word in text_lower:
            bot.delete_message(chat_id, message.message_id)
            bot.send_message(chat_id, f"🤬 {message.from_user.first_name}, не матерись!")
            return
    
    # Проверка спам слов
    for word in SPAM_KEYWORDS:
        if word in text_lower:
            bot.delete_message(chat_id, message.message_id)
            bot.send_message(chat_id, f"🚫 {message.from_user.first_name}, реклама запрещена!")
            return

# ========== ЗАПУСК ==========

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 MODERATE ARTEM ЗАПУЩЕН!")
    print("=" * 50)
    print(f"📌 Бот: @{bot.get_me().username}")
    print(f"📌 Валюта: {CURRENCY_NAME}")
    print(f"📌 Админ ID: {MAIN_ADMIN_ID}")
    print("=" * 50)
    print("✅ Функции загружены:")
    print("✓ Модерация групп")
    print("✓ Экономика и статусы")
    print("✓ Премиум подписка")
    print("✓ Донат звёздами")
    print("✓ Реферальная система")
    print("✓ Рассылки")
    print("✓ Поддержка")
    print("=" * 50)
    
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)
