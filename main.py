import telebot
from telebot import types
import schedule
import time
from datetime import datetime, timedelta
import threading
import json
from pytube import Playlist

# Конфигурация
TOKEN = 'YOUR_TOKEN'
bot = telebot.TeleBot(TOKEN)

# URL вашего плейлиста
PLAYLIST_URL = 'https://www.youtube.com/playlist?list=PLD6SPjEPomat1rP0ZZdD4VIHKSx_YhRvG'

def load_playlist_videos():
    """Загружает видео из плейлиста YouTube с ограничением времени"""
    MAX_RETRIES = 3
    MAX_VIDEOS = 200  # Максимальное количество видео для загрузки
    
    for attempt in range(MAX_RETRIES):
        try:
            playlist = Playlist(PLAYLIST_URL)
            videos = []
            
            # Получаем только URL видео без загрузки полной информации
            video_urls = list(playlist.video_urls)[:MAX_VIDEOS]
            
            for index, url in enumerate(video_urls, 1):
                videos.append({
                    'id': index,
                    'title': f'Видео {index}',  # Упрощенное название
                    'url': url
                })
                
            if videos:
                print(f"Successfully loaded {len(videos)} videos")
                return videos
                
        except Exception as e:
            print(f"Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)  # Пауза перед следующей попыткой
            continue
    
    print("Failed to load playlist after all attempts")
    return []

# Загружаем видео из плейлиста
PLAYLIST_VIDEOS = load_playlist_videos()

# Ссылки на ресурсы
SUBJECTS = {
    'информатика': {
        'name': 'Информатика',
        'link': 'https://kompege.ru/',
        'has_link': True
    },
    'русский': {
        'name': 'Русский язык',
        'link': 'https://stepik.org/course/92015/syllabus',
        'has_link': True
    },
    'математика': {
        'name': 'Математика',
        'link': None,
        'has_link': False
    }
}

@bot.message_handler(func=lambda message: message.text == '✅ Отметить выполнение')
def mark_completion(message):
    # Создаем клавиатуру с предметами из SUBJECTS
    markup = types.InlineKeyboardMarkup()
    for subject_key, subject_data in SUBJECTS.items():
        markup.add(types.InlineKeyboardButton(
            subject_data['name'],
            callback_data=f"complete_{subject_key}"
        ))
    
    bot.reply_to(message, "Выберите предмет, который вы изучили:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("complete_"))
def handle_completion(call):
    user_id = str(call.from_user.id)
    subject_key = call.data.split('_')[1]
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Инициализируем структуру если её нет
    if 'completed_tasks' not in users_data[user_id]:
        users_data[user_id]['completed_tasks'] = {}
    if today not in users_data[user_id]['completed_tasks']:
        users_data[user_id]['completed_tasks'][today] = []
    
    if subject_key not in users_data[user_id]['completed_tasks'][today]:
        users_data[user_id]['completed_tasks'][today].append(subject_key)
        save_users_data()
        response = f"✅ Предмет {SUBJECTS[subject_key]['name']} отмечен как изученный!"
    else:
        response = f"❗ Вы уже отметили {SUBJECTS[subject_key]['name']} сегодня"
    
    # Удаляем сообщение с кнопками и отправляем новое
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, response)

@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def show_statistics(message):
    user_id = str(message.from_user.id)
    
    # Создаем словарь для подсчета выполненных заданий по предметам
    subject_stats = {subject: 0 for subject in SUBJECTS.keys()}
    total_days = set()  # Для подсчета уникальных дней занятий
    
    # Собираем статистику
    for date, completed in users_data[user_id].get('completed_tasks', {}).items():
        total_days.add(date)
        for subject in completed:
            if subject in subject_stats:
                subject_stats[subject] += 1
    
    # Статистика по видео
    videos_watched = len(users_data[user_id].get('completed_videos', []))
    total_videos = len(PLAYLIST_VIDEOS)
    video_progress = (videos_watched / total_videos * 100) if total_videos > 0 else 0
    
    # Формируем ответ
    response = "📊 Ваша статистика:\n\n"
    
    # Общая статистика
    response += f"📅 Всего дней занятий: {len(total_days)}\n"
    response += f"🎥 Прогресс по видео: {videos_watched}/{total_videos} ({video_progress:.1f}%)\n\n"
    
    # Статистика по предметам
    response += "📚 По предметам:\n"
    for subject_key, count in subject_stats.items():
        response += f"- {SUBJECTS[subject_key]['name']}: {count} дней\n"
    
    # Статистика за последнюю неделю
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    recent_stats = {subject: 0 for subject in SUBJECTS.keys()}
    recent_days = 0
    
    for date, completed in users_data[user_id].get('completed_tasks', {}).items():
        if date >= week_ago:
            recent_days += 1
            for subject in completed:
                if subject in recent_stats:
                    recent_stats[subject] += 1
    
    response += "\n📅 За последнюю неделю:\n"
    response += f"- Дней занятий: {recent_days}/7\n"
    for subject_key, count in recent_stats.items():
        response += f"- {SUBJECTS[subject_key]['name']}: {count} дней\n"
    
    bot.reply_to(message, response)

# Обновляем формат данных при загрузке
def load_users_data():
    try:
        with open('users_data.json', 'r') as file:
            data = json.load(file)
            # Проверяем и инициализируем структуру для каждого пользователя
            for user_id in data:
                if 'completed_tasks' not in data[user_id]:
                    data[user_id]['completed_tasks'] = {}
                if 'completed_videos' not in data[user_id]:
                    data[user_id]['completed_videos'] = []
            return data
    except FileNotFoundError:
        return {}

def save_users_data():
    with open('users_data.json', 'w') as file:
        json.dump(users_data, file)

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id not in users_data:
        users_data[user_id] = {
            'notification_time': '16:00',
            'completed_tasks': {},
            'completed_videos': [],
            'current_video_id': 1,
            'reminders_active': True
        }
        save_users_data()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('📚 Предметы', '📺 Текущее видео')
    markup.row('✅ Отметить выполнение', '✅ Отметить просмотр')
    markup.row('📊 Статистика', '📊 Прогресс плейлиста')
    markup.row('⚙️ Настройки', '🔄 Сбросить прогресс')
    markup.row('🔔 Включить напоминания', '🔕 Выключить напоминания')
    
    bot.reply_to(message, 
                 "Привет! Я бот для планирования подготовки к экзаменам.\n"
                 "Выберите действие:", 
                 reply_markup=markup)

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
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('📚 Предметы', '📺 Текущее видео')
        markup.row('✅ Отметить выполнение', '✅ Отметить просмотр')
        markup.row('📊 Статистика', '📊 Прогресс плейлиста')
        markup.row('⚙️ Настройки', '🔄 Сбросить прогресс')
        markup.row('🔔 Включить напоминания', '🔕 Выключить напоминания')
        
        bot.reply_to(message, f"Время уведомлений установлено на {message.text}", reply_markup=markup)
        
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

@bot.message_handler(func=lambda message: message.text == '📺 Текущее видео')
def show_current_video(message):
    user_id = str(message.from_user.id)
    current_video_id = users_data[user_id]['current_video_id']
    video = next((v for v in PLAYLIST_VIDEOS if v['id'] == current_video_id), None)
    
    if video:
        response = f"🎥 {video['title']}\n\n"
        response += f"🔗 {video['url']}\n\n"
        response += "Не забудьте отметить просмотр после изучения материала!"
        bot.reply_to(message, response)
    else:
        bot.reply_to(message, "Поздравляю! Вы просмотрели весь плейлист! 🎉")

@bot.message_handler(func=lambda message: message.text == '✅ Отметить просмотр')
def mark_watched(message):
    user_id = str(message.from_user.id)
    current_video_id = users_data[user_id]['current_video_id']
    
    if current_video_id not in users_data[user_id]['completed_videos']:
        users_data[user_id]['completed_videos'].append(current_video_id)
        next_video_id = current_video_id + 1
        
        if any(v['id'] == next_video_id for v in PLAYLIST_VIDEOS):
            users_data[user_id]['current_video_id'] = next_video_id
            video = next((v for v in PLAYLIST_VIDEOS if v['id'] == next_video_id), None)
            response = "✅ Видео отмечено как просмотренное!\n\n"
            response += f"Следующее видео:\n🎥 {video['title']}"
        else:
            response = "🎉 Поздравляю! Вы просмотрели весь плейлист!"
        
        save_users_data()
        bot.reply_to(message, response)
    else:
        bot.reply_to(message, "Это видео уже отмечено как просмотренное!")

@bot.message_handler(func=lambda message: message.text == '📊 Прогресс плейлиста')
def show_progress(message):
    user_id = str(message.from_user.id)
    completed = len(users_data[user_id]['completed_videos'])
    total = len(PLAYLIST_VIDEOS)
    progress = (completed / total) * 100 if total > 0 else 0
    
    response = f"📊 Ваш прогресс по плейлисту:\n\n"
    response += f"✅ Просмотрено: {completed} из {total} видео\n"
    response += f"📈 Прогресс: {progress:.1f}%"
    bot.reply_to(message, response)

@bot.message_handler(func=lambda message: message.text == '🔄 Сбросить прогресс')
def reset_progress(message):
    user_id = str(message.from_user.id)
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Да, сбросить", callback_data="reset_yes"),
        types.InlineKeyboardButton("❌ Нет, отмена", callback_data="reset_no")
    )
    
    bot.reply_to(message, 
                "⚠️ Вы уверены, что хотите сбросить весь прогресс просмотра?\n"
                "Это действие нельзя отменить!", 
                reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("reset_"))
def reset_progress_callback(call):
    user_id = str(call.from_user.id)
    
    if call.data == "reset_yes":
        users_data[user_id]['completed_videos'] = []
        users_data[user_id]['current_video_id'] = 1
        save_users_data()
        
        video = next((v for v in PLAYLIST_VIDEOS if v['id'] == 1), None)
        response = "🔄 Прогресс успешно сброшен!\n\n"
        if video:
            response += f"Начните с первого видео:\n🎥 {video['title']}\n🔗 {video['url']}"
        
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, response)
        
    elif call.data == "reset_no":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "❌ Сброс прогресса отменен")

def send_reminder(user_id, subject_key, force=False):
    user_id_str = str(user_id)
    if not users_data[user_id_str]['reminders_active']:
        return

    current_time = datetime.now()
    today = current_time.strftime('%Y-%m-%d')
    
    if today in users_data[user_id_str].get('completed_tasks', {}) and \
       subject_key in users_data[user_id_str]['completed_tasks'][today]:
        return

    if not force:
        last_reminder = users_data[user_id_str].get('last_reminder', {}).get(subject_key)
        if last_reminder:
            last_reminder_time = datetime.fromisoformat(last_reminder)
            if (current_time - last_reminder_time).total_seconds() < 600:
                return

    subject_data = SUBJECTS[subject_key]
    message = f"🔔 Напоминание: Пора заниматься предметом {subject_data['name']}"
    if subject_data['has_link']:
        message += f"\n\nРесурс для подготовки: {subject_data['link']}"
    
    try:
        bot.send_message(user_id, message)
        if 'last_reminder' not in users_data[user_id_str]:
            users_data[user_id_str]['last_reminder'] = {}
        users_data[user_id_str]['last_reminder'][subject_key] = current_time.isoformat()
        save_users_data()
    except Exception as e:
        print(f"Error sending reminder to {user_id}: {e}")

def send_video_reminder():
    current_time = datetime.now().strftime('%H:%M')
    
    for user_id, user_data in users_data.items():
        if user_data['reminders_active'] and current_time == user_data['notification_time']:
            current_video_id = user_data['current_video_id']
            video = next((v for v in PLAYLIST_VIDEOS if v['id'] == current_video_id), None)
            
            if video:
                message = "🔔 Пора учиться!\n\n"
                message += f"Сегодняшнее видео:\n🎥 {video['title']}\n"
                message += f"🔗 {video['url']}"
                try:
                    bot.send_message(user_id, message)
                except Exception as e:
                    print(f"Error sending reminder to {user_id}: {e}")

def check_and_send_reminders():
    current_time = datetime.now()
    current_time_str = current_time.strftime('%H:%M')
    
    for user_id, user_data in users_data.items():
        if current_time_str == user_data['notification_time']:
            for subject_key in SUBJECTS.keys():
                send_reminder(user_id, subject_key, force=True)
        else:
            for subject_key in SUBJECTS.keys():
                send_reminder(user_id, subject_key)

def schedule_checker():
    while True:
        schedule.run_pending()
        check_and_send_reminders()
        send_video_reminder()
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