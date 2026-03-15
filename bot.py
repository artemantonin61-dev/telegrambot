import telebot
from telebot import types
import random
from datetime import datetime
import time
import os

# Токен бота (замени на свой)
TOKEN = "8779825034:AAHpVBWKHGk5-FS4fSZzzBwbRsxQ4L3weys"
bot = telebot.TeleBot(TOKEN)

# Хранилище данных в памяти
user_notes = {}
user_scores = {}

# ========== КЛАВИАТУРЫ ==========

def main_keyboard():
    """Главное меню"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("👤 Профиль")
    btn2 = types.KeyboardButton("📝 Заметки")
    btn3 = types.KeyboardButton("🎮 Игры")
    btn4 = types.KeyboardButton("🕒 Время")
    btn5 = types.KeyboardButton("💰 Курс валют")
    btn6 = types.KeyboardButton("🎲 Случайное число")
    btn7 = types.KeyboardButton("ℹ Помощь")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)
    return markup

def games_keyboard():
    """Меню игр"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🎯 Камень-ножницы-бумага")
    btn2 = types.KeyboardButton("🪙 Орёл-решка")
    btn3 = types.KeyboardButton("🔢 Угадай число")
    btn4 = types.KeyboardButton("🔙 Назад")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

def back_keyboard():
    """Кнопка назад"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🔙 Назад"))
    return markup

# ========== КОМАНДЫ ==========

@bot.message_handler(commands=['start'])
def start_command(message):
    """Обработка команды /start"""
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    # Инициализация данных пользователя
    if user_id not in user_notes:
        user_notes[user_id] = []
    if user_id not in user_scores:
        user_scores[user_id] = 0
    
    welcome = f"""🌟 <b>Привет, {name}!</b>

Я Telegram бот с разными функциями:

<b>📝 Заметки</b> - сохраняй важную информацию
<b>🎮 Игры</b> - камень-ножницы, орёл-решка, угадай число
<b>💰 Курс валют</b> - примерные курсы USD/EUR
<b>🕒 Время</b> - текущие дата и время
<b>🎲 Случайное число</b> - генератор чисел

Нажимай на кнопки ниже 👇"""

    bot.send_message(
        message.chat.id,
        welcome,
        parse_mode="html",
        reply_markup=main_keyboard()
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    """Помощь"""
    help_text = """<b>ℹ ПОМОЩЬ ПО БОТУ</b>

<b>📝 Заметки:</b>
• Нажми "📝 Заметки" чтобы увидеть свои заметки
• Просто напиши любой текст - он сохранится как заметка

<b>🎮 Игры:</b>
• Камень-ножницы-бумага - игра с компьютером
• Орёл-решка - случайный выбор
• Угадай число - от 1 до 10

<b>💰 Курс валют:</b>
• Примерные курсы USD и EUR

<b>🕒 Время:</b>
• Текущая дата и время

<b>🎲 Случайное число:</b>
• Число от 1 до 100"""
    
    bot.send_message(message.chat.id, help_text, parse_mode="html")

# ========== ОБРАБОТКА КНОПОК ==========

@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    """Обработка всех сообщений"""
    text = message.text
    user_id = message.from_user.id
    chat_id = message.chat.id
    name = message.from_user.first_name
    
    # Инициализация данных если нужно
    if user_id not in user_notes:
        user_notes[user_id] = []
    if user_id not in user_scores:
        user_scores[user_id] = 0
    
    # ===== ПРОФИЛЬ =====
    if text == "👤 Профиль":
        notes_count = len(user_notes[user_id])
        score = user_scores[user_id]
        
        profile = f"""<b>👤 ТВОЙ ПРОФИЛЬ</b>

🆔 ID: <code>{user_id}</code>
👤 Имя: {name}
📝 Заметок: {notes_count}
⭐ Очки: {score}

📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
        
        bot.send_message(chat_id, profile, parse_mode="html")
    
    # ===== ЗАМЕТКИ =====
    elif text == "📝 Заметки":
        if user_notes[user_id]:
            notes_list = "<b>📝 ТВОИ ЗАМЕТКИ</b>\n\n"
            for i, note in enumerate(user_notes[user_id][-10:], 1):  # Последние 10 заметок
                short_note = note[:50] + "..." if len(note) > 50 else note
                notes_list += f"{i}. {short_note}\n"
            notes_list += "\n<i>Чтобы добавить заметку, просто напиши текст</i>"
        else:
            notes_list = "<b>📝 ТВОИ ЗАМЕТКИ</b>\n\nУ тебя пока нет заметок.\n\n<i>Напиши что-нибудь, чтобы создать заметку</i>"
        
        bot.send_message(chat_id, notes_list, parse_mode="html", reply_markup=back_keyboard())
    
    # ===== ИГРЫ =====
    elif text == "🎮 Игры":
        bot.send_message(
            chat_id,
            "<b>🎮 ВЫБЕРИ ИГРУ</b>",
            parse_mode="html",
            reply_markup=games_keyboard()
        )
    
    # ===== ВРЕМЯ =====
    elif text == "🕒 Время":
        now = datetime.now()
        time_text = f"""<b>🕒 ТЕКУЩЕЕ ВРЕМЯ</b>

📅 Дата: {now.strftime('%d.%m.%Y')}
⏰ Время: {now.strftime('%H:%M:%S')}
📆 День недели: {['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'][now.weekday()]}"""
        
        bot.send_message(chat_id, time_text, parse_mode="html")
    
    # ===== КУРС ВАЛЮТ =====
    elif text == "💰 Курс валют":
        # Примерные курсы (можно заменить на реальные через API)
        usd = round(random.uniform(85, 95), 2)
        eur = round(random.uniform(90, 100), 2)
        cny = round(random.uniform(11, 13), 2)
        
        currency = f"""<b>💰 КУРСЫ ВАЛЮТ</b>

🇺🇸 USD: {usd} ₽
🇪🇺 EUR: {eur} ₽
🇨🇳 CNY: {cny} ₽

📊 Курс на {datetime.now().strftime('%d.%m.%Y')}
<i>Примерные значения</i>"""
        
        bot.send_message(chat_id, currency, parse_mode="html")
    
    # ===== СЛУЧАЙНОЕ ЧИСЛО =====
    elif text == "🎲 Случайное число":
        number = random.randint(1, 100)
        bot.send_message(
            chat_id,
            f"<b>🎲 СЛУЧАЙНОЕ ЧИСЛО</b>\n\nОт 1 до 100:\n\n<b>{number}</b>",
            parse_mode="html"
        )
    
    # ===== ПОМОЩЬ =====
    elif text == "ℹ Помощь":
        help_command(message)
    
    # ===== НАЗАД =====
    elif text == "🔙 Назад":
        bot.send_message(chat_id, "🔙 Главное меню", reply_markup=main_keyboard())
    
    # ===== КАМЕНЬ-НОЖНИЦЫ-БУМАГА =====
    elif text == "🎯 Камень-ножницы-бумага":
        rps_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        btn1 = types.KeyboardButton("🪨 Камень")
        btn2 = types.KeyboardButton("✂️ Ножницы")
        btn3 = types.KeyboardButton("📄 Бумага")
        btn4 = types.KeyboardButton("🔙 Назад")
        rps_keyboard.add(btn1, btn2, btn3, btn4)
        
        bot.send_message(
            chat_id,
            "<b>🎯 КАМЕНЬ-НОЖНИЦЫ-БУМАГА</b>\n\nСделай свой выбор:",
            parse_mode="html",
            reply_markup=rps_keyboard
        )
    
    elif text in ["🪨 Камень", "✂️ Ножницы", "📄 Бумага"]:
        user_choice = text.split()[1]
        bot_choice = random.choice(["Камень", "Ножницы", "Бумага"])
        
        # Определяем победителя
        if user_choice == bot_choice:
            result = "🤝 Ничья!"
            points = 0
        elif (user_choice == "Камень" and bot_choice == "Ножницы") or \
             (user_choice == "Ножницы" and bot_choice == "Бумага") or \
             (user_choice == "Бумага" and bot_choice == "Камень"):
            result = "✅ Ты выиграл!"
            points = 10
        else:
            result = "❌ Я выиграл!"
            points = -5
        
        user_scores[user_id] += points
        
        game_result = f"""<b>🎯 КАМЕНЬ-НОЖНИЦЫ-БУМАГА</b>

Твой выбор: {user_choice}
Мой выбор: {bot_choice}

<b>{result}</b>
{'⭐ +' + str(points) + ' очков' if points > 0 else '💔 -5 очков' if points < 0 else '⭐ 0 очков'}
Всего очков: {user_scores[user_id]}"""
        
        bot.send_message(chat_id, game_result, parse_mode="html")
    
    # ===== ОРЁЛ-РЕШКА =====
    elif text == "🪙 Орёл-решка":
        result = random.choice(["🦅 Орёл", "🪙 Решка"])
        bot.send_message(
            chat_id,
            f"<b>🪙 ОРЁЛ-РЕШКА</b>\n\nВыпало:\n\n<b>{result}</b>",
            parse_mode="html"
        )
    
    # ===== УГАДАЙ ЧИСЛО =====
    elif text == "🔢 Угадай число":
        secret_number = random.randint(1, 10)
        user_notes[f"game_{user_id}"] = secret_number  # Сохраняем загаданное число
        
        bot.send_message(
            chat_id,
            f"<b>🔢 УГАДАЙ ЧИСЛО</b>\n\nЯ загадал число от 1 до 10.\nНапиши свой вариант!",
            parse_mode="html",
            reply_markup=back_keyboard()
        )
    
    # ===== ОБРАБОТКА ТЕКСТА (УГАДАЙ ЧИСЛО И ЗАМЕТКИ) =====
    else:
        # Проверяем, не играет ли пользователь в "Угадай число"
        if f"game_{user_id}" in user_notes:
            try:
                guess = int(text)
                secret = user_notes[f"game_{user_id}"]
                
                if guess == secret:
                    user_scores[user_id] += 20
                    bot.send_message(
                        chat_id,
                        f"🎉 <b>ПОЗДРАВЛЯЮ! Ты угадал!</b>\nЧисло было {secret}\n+20 очков!",
                        parse_mode="html",
                        reply_markup=main_keyboard()
                    )
                    del user_notes[f"game_{user_id}"]  # Удаляем игру
                elif guess < secret:
                    bot.send_message(chat_id, "📉 Моё число <b>БОЛЬШЕ</b>", parse_mode="html")
                else:
                    bot.send_message(chat_id, "📈 Моё число <b>МЕНЬШЕ</b>", parse_mode="html")
            except ValueError:
                bot.send_message(chat_id, "❌ Напиши число от 1 до 10!")
        
        # Если это не игра, сохраняем как заметку
        else:
            user_notes[user_id].append(text)
            
            # Ограничиваем количество заметок до 50
            if len(user_notes[user_id]) > 50:
                user_notes[user_id] = user_notes[user_id][-50:]
            
            bot.send_message(
                chat_id,
                f"✅ <b>Заметка сохранена!</b>\n\nТекст: {text[:100]}{'...' if len(text) > 100 else ''}",
                parse_mode="html"
            )

# ========== ЗАПУСК БОТА ==========

if __name__ == "__main__":
    print("=" * 50)
    print("✅ БОТ ЗАПУЩЕН!")
    print("=" * 50)
    print(f"🤖 Имя бота: {bot.get_me().first_name}")
    print(f"🆔 ID бота: {bot.get_me().id}")
    print(f"🔗 Ссылка: https://t.me/{bot.get_me().username}")
    print("=" * 50)
    print("📌 Доступные функции:")
    print("✓ Профиль пользователя")
    print("✓ Заметки")
    print("✓ Камень-ножницы-бумага")
    print("✓ Орёл-решка")
    print("✓ Угадай число")
    print("✓ Курсы валют")
    print("✓ Время и дата")
    print("✓ Случайные числа")
    print("=" * 50)
    
    # Запуск с защитой от ошибок
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=30)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print("🔄 Перезапуск через 5 секунд...")
            time.sleep(5)