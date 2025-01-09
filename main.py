import telebot
from telebot import types
import schedule
import time
from datetime import datetime, timedelta
import threading
import json

# Конфигурация
TOKEN = 'YOUR_BOT_TOKEN'

bot = telebot.TeleBot(TOKEN)

# Ссылки на ресурсы
SUBJECTS = {
    'информатика': {
        'name': 'Информатика',
        'link': 'https://inf-ege.sdamgia.ru/',  # ссылка на нужный сайт
        'has_link': True
    },
    'русский': {
        'name': 'Русский язык',
        'link': 'https://rus-ege.sdamgia.ru/',  # ссылка на нужный сайт
        'has_link': True
    },
    'математика': {
        'name': 'Математика',
        'link': None, # мне не надо
        'has_link': False
    }
}

# Хранение данных пользователей (бд)
users_data = {}

# Загрузка данных пользователей из файла
def load_users_data():
    try:
        with open('users_data.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    
# Сохранение данных пользователей в файл
def save_users_data():
    with open('users_data.json', 'w') as file:
        json.dump(users_data, file)

# Команда start
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id not in users_data:
        users_data[user_id] = {
            'notification_time': '16:00',
            'completed_tasks': {},
            'reminders_active': True,
            'reminders_active': False
        }
        save_users_data()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('📚 Предметы', '⚙️ Настройки')
    markup.row('✅ Отметить выполнение', '📊 Статистика')
    markup.row('🔔 Включить напоминания', '🔕 Выключить напоминания')
    
    bot.reply_to(message, 
                 "Привет! Я бот для планирования подготовки к экзаменам.\n"
                 "Выберите действие:", 
                 reply_markup=markup)

# Настройка времени уведомлений
@bot.message_handler(func=lambda message: message.text == '⚙️ Настройки')
def settings(message):
    markup = types.ForceReply()
    bot.send_message(message.chat.id, 
                     f'''Введите время для ежедневных уведомлений в формате ЧЧ:ММ (например, 09:00):
Сейчас: {users_data[str(message.from_user.id)]['notification_time']}''',
                     reply_markup=markup)

@bot.message_handler(func=lambda message: message.reply_to_message and 
                    (message.reply_to_message.text.startswith("Введите время") or
                     message.reply_to_message.text.startswith("Неверный формат времени")))
def set_notification_time(message):
    try:
        time.strptime(message.text, '%H:%M')
        users_data[str(message.from_user.id)]['notification_time'] = message.text
        save_users_data()
        
        mp = types.ReplyKeyboardMarkup(resize_keyboard=True)
        
        mp.row('📚 Предметы', '⚙️ Настройки')
        mp.row('✅ Отметить выполнение', '📊 Статистика')
        mp.row('🔔 Включить напоминания', '🔕 Выключить напоминания')
        
        bot.reply_to(message, f"Время уведомлений установлено на {message.text}", reply_markup=mp)
        
    except ValueError:
        markup = types.ForceReply()
        bot.reply_to(message, "Неверный формат времени. Попробуйте снова в формате ЧЧ:ММ", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ['🔔 Включить напоминания', '🔕 Выключить напоминания'])
def toggle_reminders(message):
    user_id = str(message.from_user.id)
    if message.text == '🔔 Включить напоминания':
        users_data[user_id]['reminders_active'] = True
        bot.reply_to(message, "Напоминания включены!")
    else:
        users_data[user_id]['reminders_active'] = False
        bot.reply_to(message, "Напоминания выключены!")
    save_users_data()
    
@bot.message_handler(func=lambda message: message.text == '📚 Предметы')
def show_subjects(message):
    response = "Список предметов для подготовки:\n\n"
    for subject_key, subject_data in SUBJECTS.items():
        response += f"📖 {subject_data['name']}"
        if subject_data['has_link']:
            response += f"\n🔗 {subject_data['link']}"
        response += "\n\n"
    bot.reply_to(message, response)

def send_reminder(user_id, subject_key, force=False):
    """
    Отправка напоминания пользователю
    force=True означает отправку ежедневного напоминания (игнорирует 10-минутный интервал)
    """
    user_id_str = str(user_id)
    if not users_data[user_id_str]['reminders_active']:
        return

    current_time = datetime.now()
    today = current_time.strftime('%Y-%m-%d')
    
    # Проверяем, не выполнено ли уже задание
    if today in users_data[user_id_str].get('completed_tasks', {}) and \
       subject_key in users_data[user_id_str]['completed_tasks'][today]:
        return

    # Проверяем интервал между напоминаниями
    if not force:
        last_reminder = users_data[user_id_str].get('last_reminder', {}).get(subject_key)
        if last_reminder:
            last_reminder_time = datetime.fromisoformat(last_reminder)
            if (current_time - last_reminder_time).total_seconds() < 600:  # 10 минут
                return

    subject_data = SUBJECTS[subject_key]
    message = f"🔔 Напоминание: Пора заниматься предметом {subject_data['name']}"
    if subject_data['has_link']:
        message += f"\n\nРесурс для подготовки: {subject_data['link']}"
    
    try:
        bot.send_message(user_id, message)
        # Обновляем время последнего напоминания
        if 'last_reminder' not in users_data[user_id_str]:
            users_data[user_id_str]['last_reminder'] = {}
        users_data[user_id_str]['last_reminder'][subject_key] = current_time.isoformat()
        save_users_data()
    except Exception as e:
        print(f"Error sending reminder to {user_id}: {e}")
           
def check_and_send_reminders():
    current_time = datetime.now()
    current_time_str = current_time.strftime('%H:%M')
    
    for user_id, user_data in users_data.items():
        # Проверяем время ежедневного напоминания
        if current_time_str == user_data['notification_time']:
            for subject_key in SUBJECTS.keys():
                send_reminder(user_id, subject_key, force=True)
        # Проверяем необходимость дополнительных напоминаний
        else:
            for subject_key in SUBJECTS.keys():
                send_reminder(user_id, subject_key)
                
def schedule_checker():
    while True:
        schedule.run_pending()
        check_and_send_reminders()
        time.sleep(60)  # Проверяем каждую минуту

# Запуск проверки выполнения в отдельном потоке
if __name__ == "__main__":
    print("Bot started...")
    users_data = load_users_data()
    
    # Запускаем планировщик в отдельном потоке
    reminder_thread = threading.Thread(target=schedule_checker, daemon=True)
    reminder_thread.start()
    
    # Запускаем бота
    bot.infinity_polling()