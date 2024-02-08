import csv
import telebot
from telebot import types
from googleapiclient.discovery import build
import csv
import config

bot = telebot.TeleBot(config.bot_token)
youtube = build('youtube', 'v3', developerKey=config.youtube_api_key)

# Старт бота
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_add = types.KeyboardButton("Добавить канал")
    btn_list = types.KeyboardButton("Список каналов")
    markup.add(btn_add, btn_list)
    bot.send_message(message.chat.id, 'Привет! Выбери действие', reply_markup=markup)

# Функция обработки кнопки добавления канала
@bot.message_handler(func=lambda message: message.text == 'Добавить канал', content_types=['text'])
def add_channel(message):
    markup = types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, "Введите ID канала:", reply_markup=markup)
    bot.register_next_step_handler(message, add_channel_step)

# Функция проверки добавления канала в базу
def add_channel_step(message):
    if not check_channel_id(message.text):
        if check_channel_exists(message.text):
            channel_name, last_video_id = get_channel_info(message.text)
            add_channel_to_csv(message.text, last_video_id, channel_name)
            send_update_keyboard(message, f"Канал {channel_name} добавлен")
        else:
            send_update_keyboard(message, "Канал не существует или некорректный ID")
    else:
        send_update_keyboard(message, "Канал уже существует")

# Проверка существования канала
def check_channel_exists(channel_id):
    response = youtube.channels().list(
        part="snippet",
        id=channel_id,
        maxResults=1
    ).execute()
    return 'items' in response

def check_channel_id(message_text):
    channel_id = message_text
    with open(config.csv_file_name, mode='r', encoding='utf-8') as csv_file:
        csv_reader = csv.reader(csv_file)
        next(csv_reader, None)
        for row in csv_reader:
            if row[0] == channel_id:
                return True
        return False

def get_channel_info(channel_id):
    response = youtube.channels().list(
        part="snippet,contentDetails",
        id=channel_id,
        maxResults=1
    ).execute()
    channel = response['items'][0]
    channel_name = channel['snippet']['title']
    last_video_id = channel['contentDetails']['relatedPlaylists']['uploads']
    return channel_name, last_video_id    

def add_channel_to_csv(channel_id, last_video_id, channel_name):
    with open(config.csv_file_name, mode='a', encoding='utf-8', newline='') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow([channel_id, last_video_id, channel_name])    

@bot.message_handler(func=lambda message: message.text == 'Список каналов', content_types=['text'])
def list_channels(message):
    channels = read_channels_from_csv()
    if channels:
        markup = types.InlineKeyboardMarkup()
        for channel_id, last_video_id, channel_name in channels:
            btn_channel = types.InlineKeyboardButton(text=channel_name, callback_data=f"info_{channel_id}")
            btn_delete = types.InlineKeyboardButton(text="❌", callback_data=f"delete_{channel_id}")
            markup.add(btn_channel, btn_delete)
        bot.send_message(message.chat.id, "Список каналов:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Список каналов пуст.")

def read_channels_from_csv():
    channels = []
    with open(config.csv_file_name, mode='r', encoding='utf-8') as csv_file:
        csv_reader = csv.reader(csv_file)
        next(csv_reader, None)  
        for row in csv_reader:
            channels.append(row)
    return channels

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def callback_query(call):
    channel_id = call.data.split('_')[1]
    delete_channel_from_csv(channel_id)
    bot.answer_callback_query(call.id, "Канал удалён")
    list_channels(call.message)  # Повторно вызываем функцию списка каналов для обновления списка

def delete_channel_from_csv(channel_id):
    channels = read_channels_from_csv()
    with open(config.csv_file_name, mode='w', encoding='utf-8', newline='') as csv_file:
        csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        # Всегда записываем заголовок, независимо от того, остались ли ещё каналы
        csv_writer.writerow(['channel_id', 'last_video_id', 'channel_name'])
        for row in channels:
            if row[0] != channel_id:
                csv_writer.writerow(row)



def send_update_keyboard(message, message_text):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_add = types.KeyboardButton("Добавить канал")
    btn_list = types.KeyboardButton("Список каналов")
    markup.add(btn_add, btn_list)
    bot.send_message(message.chat.id, message_text, reply_markup=markup)



if __name__ == "__main__":
    bot.polling(none_stop=True)
