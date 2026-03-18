import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import io
import re
import math
from forex_python.converter import CurrencyRates
import random

# Токен бота
TOKEN = "8259179783:AAHuDseoX6aULdjsWPXT-zWWSNH9-nt6s6U"
bot = telebot.TeleBot(TOKEN)

# ID главного админа
MAIN_ADMIN_ID = 8779825034

# ========== БАЗА ДАННЫХ ==========

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('finance_bot.db')
    cursor = conn.cursor()
    
    # Пользователи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            created_date TEXT,
            last_active TEXT
        )
    ''')
    
    # Доходы/расходы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            category TEXT,
            amount REAL,
            description TEXT,
            date TEXT
        )
    ''')
    
    # Бюджеты по категориям
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            amount REAL,
            month TEXT,
            UNIQUE(user_id, category, month)
        )
    ''')
    
    # Задачи/напоминания
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            priority TEXT,
            category TEXT,
            deadline TEXT,
            completed INTEGER DEFAULT 0,
            created_date TEXT
        )
    ''')
    
    # Цели
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            target_amount REAL,
            current_amount REAL DEFAULT 0,
            deadline TEXT,
            created_date TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_db():
    return sqlite3.connect('finance_bot.db')

def add_user(user):
    """Добавление пользователя"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, created_date, last_active)
        VALUES (?, ?, ?, ?, ?)
    ''', (user.id, user.username, user.first_name, datetime.now().isoformat(), datetime.now().isoformat()))
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

# ========== ГЛАВНОЕ МЕНЮ ==========

def main_keyboard():
    """Главная клавиатура"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("💰 Финансы")
    btn2 = types.KeyboardButton("📋 Планировщик")
    btn3 = types.KeyboardButton("🧮 Калькулятор")
    btn4 = types.KeyboardButton("📊 Курсы валют")
    btn5 = types.KeyboardButton("🎯 Цели")
    btn6 = types.KeyboardButton("📈 Статистика")
    btn7 = types.KeyboardButton("⚙️ Настройки")
    btn8 = types.KeyboardButton("❓ Помощь")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    return markup

def finances_keyboard():
    """Клавиатура финансов"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("➕ Доход")
    btn2 = types.KeyboardButton("➖ Расход")
    btn3 = types.KeyboardButton("📊 Отчет")
    btn4 = types.KeyboardButton("📁 Категории")
    btn5 = types.KeyboardButton("💰 Баланс")
    btn6 = types.KeyboardButton("📉 График")
    btn7 = types.KeyboardButton("🔙 Назад")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)
    return markup

def planner_keyboard():
    """Клавиатура планировщика"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("📝 Добавить задачу")
    btn2 = types.KeyboardButton("📋 Мои задачи")
    btn3 = types.KeyboardButton("✅ Выполнить")
    btn4 = types.KeyboardButton("📅 Сегодня")
    btn5 = types.KeyboardButton("📊 Прогресс")
    btn6 = types.KeyboardButton("🔙 Назад")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    return markup

def calculator_keyboard():
    """Клавиатура калькулятора"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    buttons = [
        "7", "8", "9", "/",
        "4", "5", "6", "*",
        "1", "2", "3", "-",
        "0", ".", "=", "+",
        "🧮 Решить уравнение", "🔙 Назад"
    ]
    markup.add(*buttons)
    return markup

# ========== ФИНАНСЫ ==========

@bot.message_handler(func=lambda message: message.text == "💰 Финансы")
def finances_menu(message):
    """Меню финансов"""
    bot.send_message(message.chat.id, "💰 <b>Управление финансами</b>\nВыберите действие:", 
                    parse_mode='html', reply_markup=finances_keyboard())

@bot.message_handler(func=lambda message: message.text == "➕ Доход")
def add_income(message):
    """Добавление дохода"""
    msg = bot.send_message(message.chat.id, 
                          "📝 <b>Добавление дохода</b>\n\n"
                          "Введите сумму и категорию через пробел:\n"
                          "Например: <code>5000 Зарплата</code>\n"
                          "Или: <code>1000 Подработка</code>",
                          parse_mode='html')
    bot.register_next_step_handler(msg, process_income)

def process_income(message):
    """Обработка дохода"""
    try:
        parts = message.text.split()
        amount = float(parts[0])
        category = ' '.join(parts[1:]) if len(parts) > 1 else "Прочее"
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (user_id, type, category, amount, description, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (message.from_user.id, 'income', category, amount, '', datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Доход {amount}₽ в категории '{category}' добавлен!")
        
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка. Пример: 5000 Зарплата")

@bot.message_handler(func=lambda message: message.text == "➖ Расход")
def add_expense(message):
    """Добавление расхода"""
    msg = bot.send_message(message.chat.id, 
                          "📝 <b>Добавление расхода</b>\n\n"
                          "Введите сумму, категорию и описание:\n"
                          "Например: <code>1500 Еда Обед</code>\n"
                          "Или: <code>3000 Транспорт Такси</code>",
                          parse_mode='html')
    bot.register_next_step_handler(msg, process_expense)

def process_expense(message):
    """Обработка расхода"""
    try:
        parts = message.text.split()
        amount = float(parts[0])
        category = parts[1] if len(parts) > 1 else "Прочее"
        description = ' '.join(parts[2:]) if len(parts) > 2 else ""
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transactions (user_id, type, category, amount, description, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (message.from_user.id, 'expense', category, amount, description, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Расход {amount}₽ в категории '{category}' добавлен!")
        
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка. Пример: 1500 Еда Обед")

@bot.message_handler(func=lambda message: message.text == "💰 Баланс")
def show_balance(message):
    """Показать баланс"""
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = "income"', (user_id,))
    total_income = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = "expense"', (user_id,))
    total_expense = cursor.fetchone()[0] or 0
    
    cursor.execute('''
        SELECT category, SUM(amount) FROM transactions 
        WHERE user_id = ? AND type = "expense" 
        GROUP BY category ORDER BY SUM(amount) DESC LIMIT 3
    ''', (user_id,))
    top_expenses = cursor.fetchall()
    
    conn.close()
    
    balance = total_income - total_expense
    
    text = f"""<b>💰 ТЕКУЩИЙ БАЛАНС</b>

💵 Доходы: {total_income:,.0f} ₽
💸 Расходы: {total_expense:,.0f} ₽
━━━━━━━━━━━━━━━
<b>💰 Итого: {balance:,.0f} ₽</b>

<b>📊 Основные расходы:</b>
"""
    for cat, amount in top_expenses:
        text += f"• {cat}: {amount:,.0f} ₽\n"
    
    if balance > 0:
        text += f"\n✅ Можно отложить: {balance * 0.3:,.0f} ₽"
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(func=lambda message: message.text == "📊 Отчет")
def show_report(message):
    """Показать отчет за месяц"""
    user_id = message.from_user.id
    month_start = datetime.now().replace(day=1).isoformat()
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT type, SUM(amount) FROM transactions 
        WHERE user_id = ? AND date > ?
        GROUP BY type
    ''', (user_id, month_start))
    
    results = cursor.fetchall()
    conn.close()
    
    income = 0
    expense = 0
    
    for row in results:
        if row[0] == 'income':
            income = row[1]
        else:
            expense = row[1]
    
    text = f"""<b>📊 ОТЧЕТ ЗА МЕСЯЦ</b>

💰 Доходы: {income:,.0f} ₽
💸 Расходы: {expense:,.0f} ₽
━━━━━━━━━━━━━━━
💎 Остаток: {income - expense:,.0f} ₽

📊 Соотношение: {expense/income*100:.1f}% расходов
"""
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(func=lambda message: message.text == "📁 Категории")
def manage_categories(message):
    """Управление категориями"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    categories = ["Еда", "Транспорт", "Развлечения", "Здоровье", "Образование", "Одежда", "Связь", "Прочее"]
    for cat in categories:
        btn = types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}")
        markup.add(btn)
    
    bot.send_message(message.chat.id, 
                    "📁 <b>Выберите категорию для просмотра:</b>", 
                    parse_mode='html', reply_markup=markup)

# ========== ПЛАНИРОВЩИК ==========

@bot.message_handler(func=lambda message: message.text == "📋 Планировщик")
def planner_menu(message):
    """Меню планировщика"""
    bot.send_message(message.chat.id, "📋 <b>Планировщик задач</b>\nВыберите действие:", 
                    parse_mode='html', reply_markup=planner_keyboard())

@bot.message_handler(func=lambda message: message.text == "📝 Добавить задачу")
def add_task(message):
    """Добавление задачи"""
    msg = bot.send_message(message.chat.id, 
                          "📝 <b>Добавление задачи</b>\n\n"
                          "Введите задачу в формате:\n"
                          "<code>Название | Приоритет | Категория | Дедлайн</code>\n\n"
                          "Приоритет: 🔴 высокий, 🟡 средний, 🟢 низкий\n"
                          "Категория: Работа, Личное, Учеба, Здоровье\n"
                          "Дедлайн: ДД.ММ.ГГГГ\n\n"
                          "Пример: <code>Сделать отчет | 🔴 | Работа | 25.12.2024</code>",
                          parse_mode='html')
    bot.register_next_step_handler(msg, process_task)

def process_task(message):
    """Обработка задачи"""
    try:
        parts = message.text.split('|')
        if len(parts) < 4:
            raise ValueError
        
        title = parts[0].strip()
        priority = parts[1].strip()
        category = parts[2].strip()
        deadline = parts[3].strip()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (user_id, title, priority, category, deadline, created_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (message.from_user.id, title, priority, category, deadline, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Задача '{title}' добавлена!")
        
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка. Проверьте формат ввода.")

@bot.message_handler(func=lambda message: message.text == "📋 Мои задачи")
def show_tasks(message):
    """Показать все задачи"""
    user_id = message.from_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, priority, category, deadline 
        FROM tasks 
        WHERE user_id = ? AND completed = 0 
        ORDER BY 
            CASE priority
                WHEN '🔴' THEN 1
                WHEN '🟡' THEN 2
                WHEN '🟢' THEN 3
            END, deadline
    ''', (user_id,))
    
    tasks = cursor.fetchall()
    conn.close()
    
    if not tasks:
        bot.send_message(message.chat.id, "🎉 У вас нет активных задач!")
        return
    
    text = "<b>📋 АКТИВНЫЕ ЗАДАЧИ</b>\n\n"
    
    for task in tasks:
        task_id, title, priority, category, deadline = task
        deadline_str = f"📅 {deadline}" if deadline else "⏳ Без срока"
        text += f"{priority} <b>{title}</b>\n"
        text += f"  📁 {category} | {deadline_str}\n"
        text += f"  ✅ /done_{task_id}\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(func=lambda message: message.text == "📅 Сегодня")
def show_today(message):
    """Задачи на сегодня"""
    user_id = message.from_user.id
    today = datetime.now().strftime('%d.%m.%Y')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, priority, category 
        FROM tasks 
        WHERE user_id = ? AND completed = 0 AND deadline = ?
    ''', (user_id, today))
    
    tasks = cursor.fetchall()
    conn.close()
    
    if not tasks:
        bot.send_message(message.chat.id, "🎉 На сегодня задач нет!")
        return
    
    text = f"<b>📅 ЗАДАЧИ НА СЕГОДНЯ ({today})</b>\n\n"
    
    for task in tasks:
        title, priority, category = task
        text += f"{priority} {title} ({category})\n"
    
    bot.send_message(message.chat.id, text, parse_mode='html')

@bot.message_handler(func=lambda message: message.text == "✅ Выполнить")
def complete_task_prompt(message):
    """Запрос ID задачи для выполнения"""
    msg = bot.send_message(message.chat.id, 
                          "✅ <b>Выполнение задачи</b>\n\n"
                          "Введите ID задачи (можно найти в /mybots):",
                          parse_mode='html')
    bot.register_next_step_handler(msg, complete_task)

def complete_task(message):
    """Выполнение задачи"""
    try:
        task_id = int(message.text)
        user_id = message.from_user.id
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET completed = 1 WHERE id = ? AND user_id = ?', (task_id, user_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            bot.reply_to(message, "✅ Задача отмечена как выполненная!")
        else:
            bot.reply_to(message, "❌ Задача не найдена")
        
        conn.close()
        
    except ValueError:
        bot.reply_to(message, "❌ Введите число")

# ========== КАЛЬКУЛЯТОР И РЕШАТЕЛЬ УРАВНЕНИЙ ==========

@bot.message_handler(func=lambda message: message.text == "🧮 Калькулятор")
def calculator_menu(message):
    """Меню калькулятора"""
    bot.send_message(message.chat.id, 
                    "🧮 <b>Калькулятор</b>\n\n"
                    "• Простые вычисления: 2+2, 5*3, 10/2\n"
                    "• Степени: 2^3\n"
                    "• Корни: sqrt(16)\n"
                    "• Тригонометрия: sin(30), cos(60)\n"
                    "• Логарифмы: log(100), ln(10)\n\n"
                    "Просто введите выражение 👇",
                    parse_mode='html', 
                    reply_markup=calculator_keyboard())

@bot.message_handler(func=lambda message: message.text == "🧮 Решить уравнение")
def solve_equation_prompt(message):
    """Решение уравнений"""
    msg = bot.send_message(message.chat.id, 
                          "📝 <b>Решение уравнений</b>\n\n"
                          "Введите уравнение:\n"
                          "• Линейное: 2x + 5 = 15\n"
                          "• Квадратное: x^2 + 5x + 6 = 0\n"
                          "• Система: 2x+y=10, x-y=2\n\n"
                          "Пример: <code>2x + 5 = 15</code>",
                          parse_mode='html')
    bot.register_next_step_handler(msg, solve_equation)

def solve_equation(message):
    """Решение уравнения"""
    equation = message.text.strip()
    
    try:
        # Линейное уравнение ax + b = c
        if 'x' in equation and '=' in equation and '^' not in equation:
            parts = equation.split('=')
            left = parts[0].strip()
            right = parts[1].strip()
            
            # Упрощаем для линейного уравнения
            left = left.replace(' ', '').replace('x', '*x')
            right = right.replace(' ', '')
            
            # Решение для x
            result = solve_linear(equation)
            
            bot.reply_to(message, f"✅ <b>Решение:</b>\n\nx = {result}", parse_mode='html')
        
        # Квадратное уравнение
        elif 'x^2' in equation or 'x²' in equation:
            result = solve_quadratic(equation)
            bot.reply_to(message, f"✅ <b>Решение квадратного уравнения:</b>\n\n{result}", parse_mode='html')
        
        # Система уравнений
        elif ',' in equation:
            results = solve_system(equation)
            bot.reply_to(message, f"✅ <b>Решение системы:</b>\n\n{results}", parse_mode='html')
        
        else:
            # Простое выражение
            result = eval(equation.replace('^', '**'))
            bot.reply_to(message, f"✅ <b>Результат:</b>\n\n{result}", parse_mode='html')
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: не удалось решить уравнение\n\nПопробуйте другой формат")

def solve_linear(equation):
    """Решение линейного уравнения"""
    try:
        # Простой парсер для линейных уравнений
        equation = equation.replace(' ', '')
        left, right = equation.split('=')
        
        # Подставляем значения для поиска x
        # Это упрощенная версия
        import sympy as sp
        x = sp.symbols('x')
        left_expr = sp.sympify(left.replace('x', '*x'))
        right_expr = sp.sympify(right)
        solution = sp.solve(left_expr - right_expr, x)
        return solution[0] if solution else "Нет решений"
    except:
        return "Не удалось решить"

def solve_quadratic(equation):
    """Решение квадратного уравнения"""
    try:
        equation = equation.replace(' ', '').replace('²', '^2').replace('x^2', 'x**2')
        left, right = equation.split('=')
        
        import sympy as sp
        x = sp.symbols('x')
        expr = sp.sympify(left) - sp.sympify(right)
        solutions = sp.solve(expr, x)
        
        result = ""
        for i, sol in enumerate(solutions, 1):
            result += f"x{i} = {sol}\n"
        return result
    except:
        return "Не удалось решить"

def solve_system(equation):
    """Решение системы уравнений"""
    try:
        equations = equation.split(',')
        
        import sympy as sp
        x, y = sp.symbols('x y')
        
        eq1 = sp.sympify(equations[0].replace('x', '*x').replace('y', '*y'))
    