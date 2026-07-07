    import telebot
    from telebot import types
    import sqlite3
    import threading
    import time
    from datetime import datetime

    bot = telebot.TeleBot("BOT_TOKEN")

    conn = sqlite3.connect('reminders.db', check_same_thread=False)
    cur = conn.cursor()

    cur.execute('CREATE TABLE IF NOT EXISTS reminders (user_id INTEGER, time TEXT, med TEXT, dosage TEXT, status TEXT DEFAULT "active")')
    conn.commit()

    try:
        cur.execute('ALTER TABLE reminders ADD COLUMN status TEXT DEFAULT "active"')
        conn.commit()
    except:
        pass  # колонка уже существует

    # Функции БД
    def add_pill(user_id, time, med, dosage):
        cur.execute('INSERT INTO reminders (user_id, time, med, dosage, status) VALUES (?, ?, ?, ?, "active")', (user_id, time, med, dosage))
        conn.commit()

    def get_pills(now):
        # Берём только активные (не отправленные)
        cur.execute('SELECT user_id, med, dosage FROM reminders WHERE time = ? AND status = "active"', (now,))
        return cur.fetchall()

    def mark_as_sent(now, user_id):
        # Помечаем как отправленное, а не удаляем
        cur.execute('UPDATE reminders SET status = "sent" WHERE time = ? AND user_id = ?', (now, user_id))
        conn.commit()

    def checker():
        while True:
            now = datetime.now().strftime('%Y-%m-%d %H:%M')
            for uid, med, dose in get_pills(now):
                bot.send_message(uid, f'💊 ВРЕМЯ ПРИНЯТЬ!\n{med} - {dose}')
                mark_as_sent(now, uid)
            time.sleep(60)

    threading.Thread(target=checker, daemon=True).start()

    user_data = {}

    def main_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('💊 Добавить напоминание')
        btn2 = types.KeyboardButton('📋 Список напоминаний')
        markup.row(btn1, btn2)
        return markup

    @bot.message_handler(commands=['start', 'hello', 'restart'])
    def main(message):
        bot.send_message(message.chat.id, '💊 Добро пожаловать в Гиппократ - бот здоровья!', reply_markup=main_keyboard())

    @bot.message_handler(func=lambda message: message.text == '💊 Добавить напоминание')
    def button_remind(message):
        user_data[message.chat.id] = {'step': 1}
        bot.send_message(message.chat.id, 'Введите название лекарства:')

    @bot.message_handler(func=lambda message: message.text == '📋 Список напоминаний')
    def button_list(message):
        uid = message.chat.id
        cur.execute('SELECT time, med, dosage, rowid FROM reminders WHERE user_id = ? AND status = "active"', (uid,))
        pills = cur.fetchall()

        if not pills:
            bot.send_message(uid, '📭 У вас нет активных напоминаний')
        else:
            for time, med, dosage, rid in pills:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton('❌ Удалить', callback_data=f'del_{rid}'))
                bot.send_message(uid, f'💊 {med} ({dosage})\n⏰ {time}', reply_markup=markup)

    @bot.message_handler(commands=['remind'])
    def remind(message):
        user_data[message.chat.id] = {'step': 1}
        bot.send_message(message.chat.id, 'Введите название лекарства:')

    @bot.message_handler(func=lambda m: m.chat.id in user_data)
    def remind_steps(message):
        if message.text.startswith('/'):
            return

        uid = message.chat.id
        step = user_data[uid]['step']

        if step == 1:
            user_data[uid]['med'] = message.text
            user_data[uid]['step'] = 2
            bot.send_message(uid, 'Введите дозировку:')

        elif step == 2:
            user_data[uid]['dosage'] = message.text
            user_data[uid]['step'] = 3
            bot.send_message(uid, 'Введите дату и время в формате: 2026-05-26 15:22')

        elif step == 3:
            try:
                datetime.strptime(message.text, '%Y-%m-%d %H:%M')
                add_pill(uid, message.text, user_data[uid]['med'], user_data[uid]['dosage'])
                bot.send_message(uid, '✅ Напоминание сохранено!')
                del user_data[uid]
            except:
                bot.send_message(uid, '❌ Ошибка! Используйте формат: 2026-05-26 15:22')

    @bot.message_handler(content_types=['photo'])
    def get_photo(message):
        bot.reply_to(message, 'Какое красивое фото!')

    @bot.message_handler(commands=['help'])
    def help_menu(message):
        bot.send_message(message.chat.id, '📋 Команды:\n/start - Главное меню\n/remind - Добавить напоминание')

    @bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
    def delete_reminder(call):
        rid = call.data.split('_')[1]
        cur.execute('DELETE FROM reminders WHERE rowid = ?', (rid,))
        conn.commit()
        bot.send_message(call.message.chat.id, '✅ Напоминание удалено!')
        bot.delete_message(call.message.chat.id, call.message.message_id)

    bot.polling(none_stop=True)
