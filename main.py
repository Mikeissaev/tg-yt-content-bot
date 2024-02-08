
# 6523099315:AAF-sdCi2J4p4jJtSbmcJJ7Wo0oh6la1MjQ
import telebot
import sqlite3
from telebot import types

# Задаем токен вашего бота
bot_token = '6523099315:AAF-sdCi2J4p4jJtSbmcJJ7Wo0oh6la1MjQ'
bot = telebot.TeleBot(bot_token)


def db_query(query, params=(), fetch='fetchall'):
    with sqlite3.connect('channels.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch == 'fetchone':
            return cursor.fetchone()
        elif fetch == 'fetchall':
            return cursor.fetchall()
        conn.commit()


def setup_db():
    db_query(
        "CREATE TABLE IF NOT EXISTS channels (channel_id TEXT, last_video TEXT)", fetch=None)


def update_keyboard():
    channels = db_query("SELECT channel_id FROM channels")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("Добавить канал"))
    if channels:
        markup.add(types.KeyboardButton("Удалить канал"),
                   types.KeyboardButton("Вывести список каналов"))
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    setup_db()
    markup = update_keyboard()
    bot.send_message(
        message.chat.id, "Привет! Выберите действие:", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Добавить канал")
def add_channel(message):
    markup = types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, "Введите ID канала:",
                     reply_markup=markup)
    bot.register_next_step_handler(message, add_channel_step)


def add_channel_step(message):
    channel_id = message.text
    if db_query("SELECT * FROM channels WHERE channel_id=?", (channel_id,), 'fetchone'):
        # bot.send_message(message.chat.id, f"Канал {channel_id} уже добавлен!")
        send_update_keyboard(message, f"Канал {channel_id} уже добавлен!")
    else:
        db_query("INSERT INTO channels (channel_id, last_video) VALUES (?, ?)",
                 (channel_id, ""), fetch=None)
        # bot.send_message(message.chat.id, f"Канал {channel_id} успешно добавлен!")
        send_update_keyboard(message, f"Канал {channel_id} успешно добавлен!")


def send_update_keyboard(message, mes):
    markup = update_keyboard()
    bot.send_message(message.chat.id, mes, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == "Удалить канал")
def delete_channel(message):
    channels = db_query("SELECT channel_id FROM channels")
    markup = types.InlineKeyboardMarkup()
    for channel_id, in channels:
        markup.add(types.InlineKeyboardButton(
            f"Удалить {channel_id}", callback_data=f"delete_{channel_id}"))
    bot.send_message(
        message.chat.id, "Выберите канал для удаления:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def delete_channel_callback(call):
    channel_id = call.data.split('_')[1]
    db_query("DELETE FROM channels WHERE channel_id=?",
             (channel_id,), fetch=None)
    # bot.answer_callback_query(call.id, f"Канал {channel_id} удален!")
    send_update_keyboard(call.message, f"Канал {channel_id} удален!")


@bot.message_handler(func=lambda message: message.text == "Вывести список каналов")
def list_channels(message):
    channels = db_query("SELECT channel_id FROM channels")
    channel_list = "\n".join(channel_id for channel_id, in channels)
    bot.send_message(message.chat.id, f"Список каналов:\n{channel_list}")


if __name__ == "__main__":
    bot.polling(none_stop=True)


