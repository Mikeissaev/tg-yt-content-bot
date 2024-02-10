import csv
import telebot
import config
from telebot import types
from ytube import *
from loguru import logger

bot = telebot.TeleBot(config.bot_token)
logger.add("logs/debug.log", format="{time} {level} {message}", rotation="1 Mb", level="DEBUG")
logger.info('Бот запущен!')
# Старт бота
try:
    @bot.message_handler(commands=['start'])
    def start(message):
        logger.info("Авторизация...")
        user_id = message.from_user.id
        logger.info(f'Пользователь {user_id} - OK')
        if user_id not in config.admins:
            logger.error(f'Ошибка авторизации. Пользователь {user_id} не администратор.')
            bot.send_message(message.chat.id, 'Извините, у Вас нет доступа для использования этого бота.')
            return
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        btn_add = types.KeyboardButton("Добавить канал")
        btn_list = types.KeyboardButton("Список каналов")
        markup.add(btn_add, btn_list)
        bot.send_message(message.chat.id, 'Привет! Выбери действие', reply_markup=markup)
except Exception as e:
        logger.error(f'Ошибка старта бота: {e}')

# Функция обработки кнопки добавления канала
@bot.message_handler(func=lambda message: message.text == 'Добавить канал', content_types=['text'])
def add_channel(message):
    markup = types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, "Введите ссылку на канал:", reply_markup=markup)
    bot.register_next_step_handler(message, add_channel_step)


# Функция проверки и добавления канала в базу
def add_channel_step(message):
    try:
        logger.info(f'Добавление канала: {message.text}')
        logger.info('Получение ID канала...')
        channel_id = get_channel_id_by_url(message.text)
        
        if not check_channel_id(channel_id):
            if check_channel_exists(channel_id):
                channel_name, last_video_id = get_channel_info(channel_id)
                logger.info(f'Добавление канала: {channel_name}, {channel_id}')
                add_channel_to_csv(channel_id, last_video_id, channel_name)
                send_update_keyboard(message, f"Канал {channel_name} добавлен")
            else:
                logger.warning(f'Канал с ID {channel_id} не существует или некорректный ID')
                send_update_keyboard(message, "Канал не существует или некорректный ID")
        else:
            logger.warning(f'Канал с ID {channel_id} существует')
            send_update_keyboard(message, "Канал уже существует")
    except Exception as e:
          logger.error(f'Ошибка при добавлении канала: {e}')


# Создание и обработка кнопки список каналов и удаления из базы
@bot.message_handler(func=lambda message: message.text == 'Список каналов', content_types=['text'])
def list_channels(message):
    channels = read_channels_from_csv()
    logger.info(f'Запрос списка каналов...')
    if channels:
        markup = types.InlineKeyboardMarkup()
        for channel_id, last_video_id, channel_name in channels:
            btn_channel = types.InlineKeyboardButton(text=channel_name, callback_data=f"info_{channel_id}")
            btn_delete = types.InlineKeyboardButton(text="Удалить канал", callback_data=f"delete_{channel_id}")
            markup.add(btn_channel, btn_delete)
        logger.info(f'Колличество каналов: {len(channels)}')
        bot.send_message(message.chat.id, "Список каналов:", reply_markup=markup)
    else:
        logger.info(f'Список каналов пуст.')
        bot.send_message(message.chat.id, "Список каналов пуст.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def callback_query_del(call):
    channel_id = call.data.split('_')[1]
    delete_channel_from_csv(channel_id)
    bot.answer_callback_query(call.id, "Канал удалён")
    list_channels(call.message)

# Удаление канала из базы
def delete_channel_from_csv(channel_id):
    channels = read_channels_from_csv()
    try:
        with open(config.csv_file_name, mode='w', encoding='utf-8', newline='') as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            # Всегда записываем заголовок, независимо от того, остались ли ещё каналы
            csv_writer.writerow(['channel_id', 'last_video_id', 'channel_name'])
            for row in channels:
                if row[0] != channel_id:
                    csv_writer.writerow(row)
            logger.info('Канал успешно удален из базы')        
    except Exception as e:
        logger.error(f'Ошибка при удалении канала из базы: {e}')

# Проверка существования канала в базе
def check_channel_id(channel_id):
    logger.info(f'Проверка базы...')
    try:
        with open(config.csv_file_name, mode='r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file)
            next(csv_reader, None)
            for row in csv_reader:
                if row[0] == channel_id:
                    return True
            return False
    except Exception as e:
        logger.error(f'Ошибка при проверке существования канала: {e}')

# Добавление канала в базу
def add_channel_to_csv(channel_id, last_video_id, channel_name):
    try:    
        with open(config.csv_file_name, mode='a', encoding='utf-8', newline='') as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow([channel_id, last_video_id, channel_name])
            logger.info('Канал успешно добавлен в базу') 
    except Exception as e:
        logger.error(f'Ошибка при добавлении канала в базу: {e}')

# Получение списка каналов из базы
def read_channels_from_csv():
    channels = []
    try:
        with open(config.csv_file_name, mode='r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file)
            next(csv_reader, None)  
            for row in csv_reader:
                channels.append(row)
        return channels
    except Exception as e:
        logger.error(f'Ошибка при чтении каналов из базы: {e}')

# Обновление клавиатуры
def send_update_keyboard(message, message_text):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_add = types.KeyboardButton("Добавить канал")
    btn_list = types.KeyboardButton("Список каналов")
    markup.add(btn_add, btn_list)
    bot.send_message(message.chat.id, message_text, reply_markup=markup)



if __name__ == "__main__":
    bot.polling(none_stop=True)
