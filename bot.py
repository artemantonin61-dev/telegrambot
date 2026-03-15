import telebot
from telebot import types
import time
import re
from datetime import datetime, timedelta
import sqlite3
import os
from threading import Lock

# ========== НАСТРОЙКИ ==========

TOKEN = os.environ.get('BOT_TOKEN', "8779825034:AAHpVBWKHGk5-FS4fSZzzBwbRsxQ4L3weys")
bot = telebot.TeleBot(TOKEN)

# ID главного админа (твой ID)
MAIN_ADMIN_ID = 8779825034

# Настройки модерации
FLOOD_TIME = 5  # секунд между сообщениями
FLOOD_LIMIT = 5  # количество сообщений за FLOOD_TIME секунд
MAX_MESSAGE_LENGTH = 1000  # максимальная длина сообщения
MAX_URLS = 2  # максимум ссылок в сообщении

# Ключевые слова для спама/рекламы
SPAM_KEYWORDS = [
    'реклама', 'спам', 'рассылка', 'заработок', 'биткоин', 'крипта',
    'казино', 'вулкан', 'joy', 'казино', 'промокод', 'скидка', 'акция',
    'отели', 'booking', 'airbnb', 'kwork', 'фриланс', 'работа на дому'
]

# Мат-слова (замени на свои)
BAD_WORDS = [
    'хуй', 'пизда', 'блядь', 'ебать', 'сука', 'нахер', 'нахуй', 'пидор',
    'гандон', 'мудак', 'долбоеб', 'уебок', 'залупа', 'шлюха'
]

# Ссылки
LINKS_REGEX = r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)'

# ========== БАЗА ДАННЫХ ==========

def init_db():
    """Создание базы данных"""
    conn = sqlite3.connect('moderator.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Таблица настроек чатов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY,
            welcome_message TEXT,
            rules TEXT,
            flood_protection INTEGER DEFAULT 1,
            spam_filter INTEGER DEFAULT 1,
            link_filter INTEGER DEFAULT 1,
            bad_words_filter INTEGER DEFAULT 1,
            captcha_enabled INTEGER DEFAULT 0,
            log_channel_id INTEGER,
            welcome_enabled INTEGER DEFAULT 1
        )
    ''')
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            chat_id INTEGER,
            warns INTEGER DEFAULT 0,
            muted_until TEXT,
            joined_date TEXT,
            messages_count INTEGER DEFAULT 0,
            last_message_time REAL,
            PRIMARY KEY (user_id, chat_id)
        )
    ''')
    
    # Таблица для фильтров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            filter_text TEXT,
            filter_type TEXT,  -- 'word', 'link', 'regex'
            action TEXT,  -- 'delete', 'warn', 'ban'
            created_by INTEGER
        )
    ''')
    
    # Таблица для логов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS moderation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            action TEXT,
            user_id INTEGER,
            admin_id INTEGER,
            reason TEXT,
            timestamp TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_db():
    """Получить соединение с БД"""
    return sqlite3.connect('moderator.db', check_same_thread=False)

def log_action(chat_id, action, user_id, admin_id=None, reason=""):
    """Запись действия в лог"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO moderation_logs (chat_id, action, user_id, admin_id, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (chat_id, action, user_id, admin_id, reason, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass

def is_admin(message):
    """Проверка, является ли пользователь администратором чата"""
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Главный админ всегда имеет права
        if user_id == MAIN_ADMIN_ID:
            return True
        
        # Проверяем права в чате
        chat_member = bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator']
    except:
        return False

def is_admin_id(chat_id, user_id):
    """Проверка по ID"""
    try:
        if user_id == MAIN_ADMIN_ID:
            return True
        chat_member = bot.get_chat_member(chat_id, user_id)
        return chat_member.status in ['administrator', 'creator']
    except:
        return False

def get_chat_settings(chat_id):
    """Получить настройки чата"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM chat_settings WHERE chat_id = ?', (chat_id,))
    settings = cursor.fetchone()
    conn.close()
    
    if not settings:
        return {
            'welcome_message': 'Добро пожаловать в чат!',
            'rules': 'Правила чата: 1. Уважайте друг друга 2. Не спамить 3. Не материться',
            'flood_protection': 1,
            'spam_filter': 1,
            'link_filter': 1,
            'bad_words_filter': 1,
            'captcha_enabled': 0,
            'log_channel_id': None,
            'welcome_enabled': 1
        }
    
    return {
        'welcome_message': settings[1],
        'rules': settings[2],
        'flood_protection': settings[3],
        'spam_filter': settings[4],
        'link_filter': settings[5],
        'bad_words_filter': settings[6],
        'captcha_enabled': settings[7],
        'log_channel_id': settings[8],
        'welcome_enabled': settings[9]
    }

def update_user_stats(chat_id, user_id):
    """Обновить статистику пользователя"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        current_time = time.time()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, chat_id, messages_count, last_message_time, joined_date)
            VALUES (?, ?, COALESCE((SELECT messages_count FROM users WHERE user_id = ? AND chat_id = ?), 0) + 1, ?, 
            COALESCE((SELECT joined_date FROM users WHERE user_id = ? AND chat_id = ?), ?))
        ''', (user_id, chat_id, user_id, chat_id, current_time, user_id, chat_id, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    except:
        pass

def check_flood(chat_id, user_id):
    """Проверка на флуд"""
    conn = get_db()
    cursor = conn.cursor()
    
    settings = get_chat_settings(chat_id)
    if not settings['flood_protection']:
        conn.close()
        return False
    
    current_time = time.time()
    
    cursor.execute('''
        SELECT last_message_time FROM users 
        WHERE user_id = ? AND chat_id = ?
    ''', (user_id, chat_id))
    
    result = cursor.fetchone()
    
    if result:
        last_time = result[0]
        time_diff = current_time - last_time
        
        if time_diff < FLOOD_TIME:
            conn.close()
            return True
    
    conn.close()
    return False

def check_spam(text):
    """Проверка на спам по ключевым словам"""
    if not text:
        return False
    text_lower = text.lower()
    for word in SPAM_KEYWORDS:
        if word in text_lower:
            return True
    return False

def check_bad_words(text):
    """Проверка на мат"""
    if not text:
        return False
    text_lower = text.lower()
    for word in BAD_WORDS:
        if word in text_lower:
            return True
    return False

def count_links(text):
    """Подсчет ссылок в тексте"""
    if not text:
        return 0
    return len(re.findall(LINKS_REGEX, text, re.IGNORECASE))

def is_user_muted(chat_id, user_id):
    """Проверка, замьючен ли пользователь"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT muted_until FROM users WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            muted_until = datetime.fromisoformat(result[0])
            if datetime.now() < muted_until:
                return True
    except:
        pass
    return False

# ========== КОМАНДЫ ДЛЯ ГРУПП ==========

@bot.message_handler(commands=['start'])
def start_command(message):
    """Запуск бота"""
    if message.chat.type == 'private':
        bot.reply_to(message, 
            "🤖 <b>Бот-модератор для групп</b>\n\n"
            "Добавь меня в группу и дай права администратора, чтобы я мог:\n"
            "• Удалять спам и рекламу\n"
            "• Банить нарушителей\n"
            "• Приветствовать новых участников\n"
            "• Защищать от флуда\n\n"
            "Команды для админов:\n"
            "/settings - настройки чата\n"
            "/ban - забанить (ответом на сообщение)\n"
            "/mute - замьютить (ответом)\n"
            "/unmute - размьютить\n"
            "/warn - предупреждение\n"
            "/rules - правила чата\n"
            "/clear - очистить сообщения",
            parse_mode='html')
    else:
        bot.reply_to(message, "🤖 Бот-модератор активен! Используй /help для списка команд")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Помощь"""
    if message.chat.type == 'private':
        return
    
    if is_admin(message):
        help_text = """<b>🔰 КОМАНДЫ АДМИНИСТРАТОРА</b>

<b>Модерация:</b>
/ban [причина] - заблокировать пользователя (ответом)
/mute [время в мин] [причина] - ограничить (ответом)
/unmute - снять ограничение (ответом)
/kick - выгнать (ответом)
/warn [причина] - выдать предупреждение (ответом)
/unwarn - снять предупреждение (ответом)
/clear [количество] - удалить сообщения

<b>Управление:</b>
/settings - настройки чата
/rules - показать правила
/setrules [текст] - установить правила
/setwelcome [текст] - установить приветствие
/logchannel [id] - канал для логов
/stats - статистика чата

<b>Фильтры:</b>
/addfilter [текст] - добавить фильтр
/delfilter [id] - удалить фильтр
/filters - список фильтров
"""
    else:
        help_text = """<b>🔰 ДОСТУПНЫЕ КОМАНДЫ</b>

/rules - правила чата
/stats - статистика
/report [причина] - пожаловаться на сообщение

Для администраторов доступны команды модерации."""
    
    bot.reply_to(message, help_text, parse_mode='html')

@bot.message_handler(commands=['settings'])
def settings_command(message):
    """Настройки чата"""
    if not is_admin(message):
        bot.reply_to(message, "❌ Только админы могут менять настройки")
        return
    
    chat_id = message.chat.id
    settings = get_chat_settings(chat_id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопки настроек
    flood_status = "✅" if settings['flood_protection'] else "❌"
    spam_status = "✅" if settings['spam_filter'] else "❌"
    link_status = "✅" if settings['link_filter'] else "❌"
    word_status = "✅" if settings['bad_words_filter'] else "❌"
    welcome_status = "✅" if settings['welcome_enabled'] else "❌"
    
    btn1 = types.InlineKeyboardButton(f"{flood_status} Антифлуд", callback_data="toggle_flood")
    btn2 = types.InlineKeyboardButton(f"{spam_status} Антиспам", callback_data="toggle_spam")
    btn3 = types.InlineKeyboardButton(f"{link_status} Фильтр ссылок", callback_data="toggle_links")
    btn4 = types.InlineKeyboardButton(f"{word_status} Фильтр мата", callback_data="toggle_words")
    btn5 = types.InlineKeyboardButton(f"{welcome_status} Приветствие", callback_data="toggle_welcome")
    btn6 = types.InlineKeyboardButton("📝 Правила", callback_data="show_rules")
    btn7 = types.InlineKeyboardButton("📊 Статистика", callback_data="chat_stats")
    btn8 = types.InlineKeyboardButton("❌ Закрыть", callback_data="close_settings")
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    
    settings_text = f"""<b>⚙️ НАСТРОЙКИ ЧАТА</b>

Текущие параметры:
🛡 Антифлуд: {flood_status}
🚫 Антиспам: {spam_status}
🔗 Фильтр ссылок: {link_status}
🤬 Фильтр мата: {word_status}
👋 Приветствие: {welcome_status}

Нажми на кнопку для изменения настройки."""
    
    bot.send_message(chat_id, settings_text, parse_mode='html', reply_markup=markup)

@bot.message_handler(commands=['ban'])
def ban_command(message):
    """Бан пользователя"""
    if not is_admin(message):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение пользователя")
        return
    
    user_to_ban = message.reply_to_message.from_user
    chat_id = message.chat.id
    admin_id = message.from_user.id
    
    # Проверяем, не админ ли цель
    if is_admin_id(chat_id, user_to_ban.id):
        bot.reply_to(message, "❌ Нельзя забанить администратора")
        return
    
    reason = message.text.replace('/ban', '').strip() or 'Нарушение правил'
    
    try:
        bot.ban_chat_member(chat_id, user_to_ban.id)
        
        # Уведомление
        bot.send_message(chat_id, 
            f"🔨 <b>БАН</b>\n"
            f"Пользователь: {user_to_ban.first_name}\n"
            f"Причина: {reason}\n"
            f"Админ: {message.from_user.first_name}",
            parse_mode='html')
        
        # Лог
        log_action(chat_id, 'ban', user_to_ban.id, admin_id, reason)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['mute'])
def mute_command(message):
    """Мут пользователя"""
    if not is_admin(message):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение пользователя")
        return
    
    user_to_mute = message.reply_to_message.from_user
    chat_id = message.chat.id
    admin_id = message.from_user.id
    
    if is_admin_id(chat_id, user_to_mute.id):
        bot.reply_to(message, "❌ Нельзя замьютить администратора")
        return
    
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
        
        # Сохраняем в БД
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, chat_id, muted_until)
            VALUES (?, ?, ?)
        ''', (user_to_mute.id, chat_id, until_date.isoformat()))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id,
            f"🔇 <b>МУТ</b>\n"
            f"Пользователь: {user_to_mute.first_name}\n"
            f"Время: {mute_time} мин\n"
            f"Причина: {reason}\n"
            f"Админ: {message.from_user.first_name}",
            parse_mode='html')
        
        log_action(chat_id, 'mute', user_to_mute.id, admin_id, reason)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unmute'])
def unmute_command(message):
    """Снятие мута"""
    if not is_admin(message):
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
        
        # Удаляем из БД
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET muted_until = NULL WHERE user_id = ? AND chat_id = ?', 
                      (user_to_unmute.id, chat_id))
        conn.commit()
        conn.close()
        
        bot.send_message(chat_id,
            f"🔊 <b>МУТ СНЯТ</b>\n"
            f"Пользователь: {user_to_unmute.first_name}\n"
            f"Админ: {message.from_user.first_name}",
            parse_mode='html')
        
        log_action(chat_id, 'unmute', user_to_unmute.id, message.from_user.id)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['warn'])
def warn_command(message):
    """Предупреждение"""
    if not is_admin(message):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "❌ Ответь на сообщение пользователя")
        return
    
    user = message.reply_to_message.from_user
    chat_id = message.chat.id
    reason = message.text.replace('/warn', '').strip() or 'Нарушение правил'
    
    if is_admin_id(chat_id, user.id):
        bot.reply_to(message, "❌ Нельзя выдать предупреждение администратору")
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO users (user_id, chat_id, warns)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, chat_id) DO UPDATE SET
        warns = warns + 1
    ''', (user.id, chat_id))
    
    conn.commit()
    
    cursor.execute('SELECT warns FROM users WHERE user_id = ? AND chat_id = ?', (user.id, chat_id))
    warns = cursor.fetchone()[0]
    conn.close()
    
    bot.send_message(chat_id,
        f"⚠️ <b>ПРЕДУПРЕЖДЕНИЕ</b>\n"
        f"Пользователь: {user.first_name}\n"
        f"Предупреждений: {warns}/3\n"
        f"Причина: {reason}\n"
        f"Админ: {message.from_user.first_name}",
        parse_mode='html')
    
    log_action(chat_id, 'warn', user.id, message.from_user.id, reason)
    
    # Автобан после 3 предупреждений
    if warns >= 3:
        try:
            bot.ban_chat_member(chat_id, user.id)
            bot.send_message(chat_id,
                f"🔨 <b>АВТОМАТИЧЕСКИЙ БАН</b>\n"
                f"Пользователь {user.first_name} забанен за 3 предупреждения",
                parse_mode='html')
        except:
            pass

@bot.message_handler(commands=['rules'])
def rules_command(message):
    """Показать правила"""
    chat_id = message.chat.id
    settings = get_chat_settings(chat_id)
    
    rules_text = f"""<b>📜 ПРАВИЛА ЧАТА</b>

{settings['rules']}

Нарушение правил влечет за собой:
⚠️ Предупреждение
🔇 Мут
🔨 Бан"""
    
    bot.reply_to(message, rules_text, parse_mode='html')

@bot.message_handler(commands=['setrules'])
def setrules_command(message):
    """Установить правила"""
    if not is_admin(message):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    chat_id = message.chat.id
    new_rules = message.text.replace('/setrules', '').strip()
    
    if not new_rules:
        bot.reply_to(message, "❌ Напиши текст правил")
        return
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO chat_settings (chat_id, rules)
        VALUES (?, ?)
    ''', (chat_id, new_rules))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, "✅ Правила обновлены!")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    """Статистика чата"""
    chat_id = message.chat.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Общая статистика
    cursor.execute('SELECT COUNT(*) FROM users WHERE chat_id = ?', (chat_id,))
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(messages_count) FROM users WHERE chat_id = ?', (chat_id,))
    total_messages = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM moderation_logs WHERE chat_id = ?', (chat_id,))
    total_mod_actions = cursor.fetchone()[0]
    
    cursor.execute('SELECT user_id, messages_count FROM users WHERE chat_id = ? ORDER BY messages_count DESC LIMIT 5', (chat_id,))
    top_chatters = cursor.fetchall()
    
    conn.close()
    
    stats_text = f"""<b>📊 СТАТИСТИКА ЧАТА</b>

👥 Всего участников: {total_users}
💬 Всего сообщений: {total_messages}
🛡 Действий модерации: {total_mod_actions}

<b>Топ чаттеров:</b>
"""
    for i, (user_id, count) in enumerate(top_chatters, 1):
        try:
            user = bot.get_chat_member(chat_id, user_id).user
            name = user.first_name
        except:
            name = "Неизвестный"
        stats_text += f"{i}. {name}: {count} сообщ.\n"
    
    bot.reply_to(message, stats_text, parse_mode='html')

@bot.message_handler(commands=['clear'])
def clear_command(message):
    """Очистка сообщений"""
    if not is_admin(message):
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    chat_id = message.chat.id
    args = message.text.split()
    
    try:
        count = int(args[1]) if len(args) > 1 else 10
        count = min(count, 100)  # Не больше 100 за раз
        
        # Удаляем команду
        bot.delete_message(chat_id, message.message_id)
        
        # Удаляем указанное количество сообщений
        for i in range(count):
            try:
                bot.delete_message(chat_id, message.message_id - i - 1)
            except:
                pass
        
        bot.send_message(chat_id, f"✅ Удалено {count} сообщений")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ========== ОБРАБОТКА НОВЫХ УЧАСТНИКОВ ==========

@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    """Приветствие новых участников"""
    for new_member in message.new_chat_members:
        if new_member.id == bot.get_me().id:
            # Бота добавили в группу
            bot.send_message(message.chat.id,
                "🤖 <b>Спасибо что добавили меня!</b>\n"
                "Выдайте мне права администратора для работы.\n"
                "/settings - настройки чата",
                parse_mode='html')
            return
        
        chat_id = message.chat.id
        settings = get_chat_settings(chat_id)
        
        if settings['welcome_enabled']:
            welcome = settings['welcome_message'].replace('{name}', new_member.first_name)
            
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton("📜 Правила", callback_data="show_rules")
            markup.add(btn)
            
            bot.send_message(chat_id, welcome, parse_mode='html', reply_markup=markup)
        
        # Сохраняем в БД
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, chat_id, joined_date)
            VALUES (?, ?, ?)
        ''', (new_member.id, chat_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()

@bot.message_handler(content_types=['left_chat_member'])
def goodbye_member(message):
    """Прощание при выходе"""
    left_member = message.left_chat_member
    if left_member.id != bot.get_me().id:
        bot.send_message(message.chat.id, f"👋 Пользователь {left_member.first_name} покинул чат")

# ========== МОДЕРАЦИЯ СООБЩЕНИЙ ==========

@bot.message_handler(func=lambda message: message.chat.type != 'private')
def moderate_message(message):
    """Модерация сообщений"""
    if not message.text:
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text
    
    settings = get_chat_settings(chat_id)
    
    # Обновляем статистику
    update_user_stats(chat_id, user_id)
    
    # Проверка на мут
    if is_user_muted(chat_id, user_id):
        bot.delete_message(chat_id, message.message_id)
        bot.send_message(chat_id, f"🔇 {message.from_user.first_name}, у вас мут. Нельзя писать.")
        return
    
    # Пропускаем админов
    if is_admin_id(chat_id, user_id):
        return
    
    reasons = []
    
    # Антифлуд
    if settings['flood_protection'] and check_flood(chat_id, user_id):
        reasons.append("Флуд")
        bot.delete_message(chat_id, message.message_id)
        bot.send_message(chat_id, f"⚠️ {message.from_user.first_name}, не флуди!")
        return
    
    # Фильтр ссылок
    if settings['link_filter']:
        link_count = count_links(text)
        if link_count > MAX_URLS:
            reasons.append(f"Ссылки ({link_count})")
            bot.delete_message(chat_id, message.message_id)
    
    # Фильтр спама
    if settings['spam_filter'] and check_spam(text):
        reasons.append("Спам/Реклама")
        bot.delete_message(chat_id, message.message_id)
    
    # Фильтр мата
    if settings['bad_words_filter'] and check_bad_words(text):
        reasons.append("Мат")
        bot.delete_message(chat_id, message.message_id)
    
    # Длина сообщения
    if len(text) > MAX_MESSAGE_LENGTH:
        reasons.append("Слишком длинное сообщение")
        bot.delete_message(chat_id, message.message_id)
    
    # Если есть нарушения
    if reasons:
        reason_text = ", ".join(reasons)
        warning = bot.send_message(chat_id,
            f"⚠️ {message.from_user.first_name}, ваше сообщение удалено!\nПричина: {reason_text}")
        
        log_action(chat_id, 'auto_delete', user_id, reason=reason_text)

# ========== ОБРАБОТКА КНОПОК ==========

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    if call.data == "toggle_flood":
        settings = get_chat_settings(chat_id)
        new_value = 0 if settings['flood_protection'] else 1
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO chat_settings (chat_id, flood_protection)
            VALUES (?, ?)
        ''', (chat_id, new_value))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, f"Антифлуд {'включен' if new_value else 'выключен'}")
        settings_command(call.message)  # Обновляем сообщение
        
    elif call.data == "toggle_spam":
        settings = get_chat_settings(chat_id)
        new_value = 0 if settings['spam_filter'] else 1
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO chat_settings (chat_id, spam_filter)
            VALUES (?, ?)
        ''', (chat_id, new_value))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, f"Антиспам {'включен' if new_value else 'выключен'}")
        settings_command(call.message)
        
    elif call.data == "toggle_links":
        settings = get_chat_settings(chat_id)
        new_value = 0 if settings['link_filter'] else 1
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO chat_settings (chat_id, link_filter)
            VALUES (?, ?)
        ''', (chat_id, new_value))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, f"Фильтр ссылок {'включен' if new_value else 'выключен'}")
        settings_command(call.message)
        
    elif call.data == "toggle_words":
        settings = get_chat_settings(chat_id)
        new_value = 0 if settings['bad_words_filter'] else 1
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO chat_settings (chat_id, bad_words_filter)
            VALUES (?, ?)
        ''', (chat_id, new_value))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, f"Фильтр мата {'включен' if new_value else 'выключен'}")
        settings_command(call.message)
        
    elif call.data == "toggle_welcome":
        settings = get_chat_settings(chat_id)
        new_value = 0 if settings['welcome_enabled'] else 1
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO chat_settings (chat_id, welcome_enabled)
            VALUES (?, ?)
        ''', (chat_id, new_value))
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, f"Приветствие {'включено' if new_value else 'выключено'}")
        settings_command(call.message)
        
    elif call.data == "show_rules":
        settings = get_chat_settings(chat_id)
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, 
            f"<b>📜 ПРАВИЛА ЧАТА</b>\n\n{settings['rules']}", 
            parse_mode='html')
        
    elif call.data == "chat_stats":
        bot.answer_callback_query(call.id)
        stats_command(call.message)
        
    elif call.data == "close_settings":
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id, message_id)

# ========== ЗАПУСК ==========

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 БОТ-МОДЕРАТОР ЗАПУЩЕН!")
    print("=" * 50)
    print(f"🤖 Имя: {bot.get_me().first_name}")
    print(f"🆔 ID: {bot.get_me().id}")
    print("=" * 50)
    print("📌 Функции модерации:")
    print("✓ Бан / Мут / Кик")
    print("✓ Антифлуд")
    print("✓ Фильтр ссылок")
    print("✓ Фильтр мата")
    print("✓ Приветствие")
    print("✓ Статистика")
    print("=" * 50)
    
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(5)
