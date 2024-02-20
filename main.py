import csv
import telebot
import schedule
import time
from threading import Thread
from telebot import types
from ytube import *
from loguru import logger
import datetime
import configparser

try:
    config = configparser.ConfigParser()
    config.read('config.ini')

    csv_file_name = config.get('Settings', 'csv_file_name')
    channel = config.get('Settings', 'channel')
    check_interval = config.get('Settings', 'check_interval')
    bot_token = config.get('Settings', 'bot_token')
    check_publication_date = config.getboolean('Settings', 'check_publication_date')
    admin = config.get('Settings', 'admin')
    moderation_mode = config.getboolean('Settings','moderation_mode')

    bot = telebot.TeleBot(bot_token)

    logger.add("logs/debug.log", format="{time} {level} {message}", rotation="1 Mb", level="DEBUG")
    logger.info('Бот запущен!')


    # Старт бота
    try:
        @bot.message_handler(commands=['start'])
        def start(message):
            logger.info("Авторизация...")
            user_id = message.from_user.id
            if user_id == admin:
                logger.error(f'Ошибка авторизации. Пользователь {user_id} не администратор.')
                bot.send_message(message.chat.id, 'Извините, у Вас нет доступа для использования этого бота.')
                return
            logger.info(f'Пользователь {user_id} - OK')
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            btn_add = types.KeyboardButton("Добавить канал")
            btn_list = types.KeyboardButton("Список каналов")
            btn_check = types.KeyboardButton("Проверить новые публикации")
            markup.add(btn_add)
            markup.add(btn_list)
            markup.add(btn_check)        
            bot.send_message(message.chat.id, 'Привет! Выбери действие', reply_markup=markup)
    except Exception as e:
            logger.error(f'Ошибка старта бота: {e}')

    # Функция обработки кнопки добавления канала
    @bot.message_handler(func=lambda message: message.text == 'Добавить канал', content_types=['text'])
    def add_channel(message):
        markup = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, "Введите ссылку на канал:", reply_markup=markup)
        bot.register_next_step_handler(message, add_channel_step)

    @bot.message_handler(func=lambda message: message.text == 'Проверить новые публикации', content_types=['text'])
    def check_new_video_btn(message):
        check_last_video()
        send_update_keyboard(message, "Проверка завершена 👌")
        

    # Функция проверки и добавления канала в базу
    def add_channel_step(message):
        try:
            logger.info(f'Добавление канала: {message.text}')
            logger.info('Получение ID канала...')
            channel_id = get_channel_id_by_url(message.text)

            if not check_channel_id(channel_id):
                if check_channel_exists(channel_id):
                    channel_name, last_video_id, date = get_channel_info(channel_id)
                    logger.info(f'Добавление канала: {channel_name}, {channel_id}')
                    add_channel_to_csv(channel_id, last_video_id, channel_name)
                    send_update_keyboard(message, f"Канал {channel_name} добавлен")
                else:
                    logger.warning(f'Канал с ID {channel_id} не существует или некорректный ID')
                    send_update_keyboard(message, "Канал не существует или некорректный ID")
            else:
                logger.warning(f'Канал с ID {channel_id} уже добавлен')
                send_update_keyboard(message, "Канал уже добавлен")
        except Exception as e:
              logger.error(f'Ошибка при добавлении канала: {e}')



    # Создание и обработка кнопки список каналов и удаления из базы
    @bot.message_handler(func=lambda message: message.text == 'Список каналов', content_types=['text'])
    def list_channels(message):
        channels = read_channels_from_csv()
        logger.info(f'Запрос списка каналов...')
        if channels:
            markup = types.InlineKeyboardMarkup()
            for row in channels:
                # Убедимся, что в строке есть достаточно данных для распаковки
                if len(row) >= 3:
                    channel_id, last_video_id, channel_name = row[0], row[1], row[2]
                    btn_channel = types.InlineKeyboardButton(text=channel_name, callback_data=f"info_{channel_id}")
                    btn_delete = types.InlineKeyboardButton(text="Удалить канал", callback_data=f"delete_{channel_id}")
                    markup.add(btn_channel, btn_delete)
                else:
                    logger.warning(f'Некорректный формат строки в базе: {row}')
            if markup.keyboard:
                logger.info(f'Количество каналов: {len(markup.keyboard)}')
                bot.send_message(message.chat.id, "Список каналов:", reply_markup=markup)
            else:
                logger.info('Список каналов пуст.')
                bot.send_message(message.chat.id, "Список каналов пуст.")
        else:
            logger.info('Список каналов пуст.')
            bot.send_message(message.chat.id, "Список каналов пуст.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
    def callback_query_del(call):
        logger.debug(call.data)
        channel_id = call.data.split("delete_", 1)[1]
        delete_channel_from_csv(channel_id)
        bot.answer_callback_query(call.id, "Канал удалён")
        list_channels(call.message)

    # Удаление канала из базы
    def delete_channel_from_csv(channel_id):
        logger.info(channel_id)
        channels = read_channels_from_csv()
        try:
            with open(csv_file_name, mode='w', encoding='utf-8', newline='') as csv_file:
                csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                # Всегда записываем заголовок, независимо от того, остались ли ещё каналы
                csv_writer.writerow(['channel_id', 'last_video_id', 'channel_name'])
                for row in channels:
                    if row[0] != channel_id:
                        csv_writer.writerow(row)
                logger.info(f'Канал {channel_id} успешно удален из базы')        
        except Exception as e:
            logger.error(f'Ошибка при удалении канала из базы: {e}')

    # Проверка существования канала в базе
    def check_channel_id(channel_id):
        logger.info('Проверка базы...')
        try:
            with open(csv_file_name, mode='r', encoding='utf-8') as csv_file:
                csv_reader = csv.reader(csv_file)
                next(csv_reader, None)  # Пропускаем заголовок, если он есть
                for row in csv_reader:
                    # Проверяем, что строка содержит хотя бы один элемент
                    if len(row) > 0 and row[0] == channel_id:
                        return True
                return False
        except Exception as e:
            logger.error(f'Ошибка при проверке существования канала: {e}')

    # Добавление канала в базу
    def add_channel_to_csv(channel_id, last_video_id, channel_name):
        try:    
            with open(csv_file_name, mode='a', encoding='utf-8', newline='') as csv_file:
                csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                csv_writer.writerow([channel_id, last_video_id, channel_name])
                logger.info('Канал успешно добавлен в базу') 
        except Exception as e:
            logger.error(f'Ошибка при добавлении канала в базу: {e}')

    # Получение списка каналов из базы
    def read_channels_from_csv():
        channels = []
        try:
            with open(csv_file_name, mode='r', encoding='utf-8') as csv_file:
                csv_reader = csv.reader(csv_file)
                next(csv_reader, None)  
                for row in csv_reader:
                    channels.append(row)
            return channels
        except Exception as e:
            logger.error(f'Ошибка при чтении каналов из базы: {e}')

    # Проверка обновлений видео
    def check_last_video():
        logger.info('Запуск проверки обновлений видео...')
        channels = read_channels_from_csv()
        for channel in channels:
            channel_id, last_video_id, channel_name = channel[0], channel[1], channel[2]
            logger.info(f'Проверка канала: {channel_name}')
            real_channel_name, new_video_id, publish_date = get_channel_info(channel_id)
            if new_video_id != last_video_id:
                logger.warning(f'Новое видео!')
                today = datetime.date.today()
                if check_publication_date:
                    logger.info(f'Проверка даты публикации...')
                    if publish_date == today:
                        send_on_moderation(channel_id, real_channel_name, new_video_id)
                    else:
                        logger.warning(f'Видео опубликовано не сегодня')
                else:
                    send_on_moderation(channel_id, new_video_id, real_channel_name)
                change_last_video_id(channel_id, new_video_id, real_channel_name)


    # Премодерация публикации
    def send_on_moderation(channel_id, new_video_id, channel_name):
        if moderation_mode:
            logger.info(f"Отправка видео на модерацию")
            msg = f"На канале <b>{channel_name}</b> опубликовано <a href='https://www.youtube.com/watch?v={new_video_id}'><b><i>НОВОЕ ВИДЕО:</i></b></a> "

            markup = types.InlineKeyboardMarkup()
            btn_publish = types.InlineKeyboardButton("Опубликовать", callback_data=f"publish_{channel_id}")
            markup.add(btn_publish)
            bot.send_message(admin, msg, reply_markup=markup, parse_mode='HTML')
        else:
            public_new_video(channel_name, new_video_id)

    # Обработка нажатия кнопки "Опубликовать"
    @bot.callback_query_handler(func=lambda call: call.data.startswith('publish_'))
    def callback_query_publish(call):
        channel_id = call.data.split("publish_", 1)[1]
        channel_name, new_video_id, date = get_channel_info(channel_id)
        public_new_video(channel_name, new_video_id)
        logger.info(f'Видео опубликовано!')


    # Обновление последнего видео в базе
    def change_last_video_id(channel_id, last_video_id, channel_name):
        try:
            # Считывание всего содержимого файла
            rows = []
            with open(csv_file_name, mode='r', encoding='utf-8') as csv_file:
                csv_reader = csv.reader(csv_file)
                for row in csv_reader:
                    if row:  # Проверка на пустую строку
                        # Если ID канала совпадает, обновляем last_video_id
                        if row[0] == channel_id:
                            row[1] = last_video_id
                            logger.info(f'Канал {channel_name} успешно обновлен')
                        rows.append(row)

            # Перезапись файла с обновленными данными
            with open(csv_file_name, mode='w', encoding='utf-8', newline='') as csv_file:
                csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                csv_writer.writerows(rows)

        except Exception as e:
            logger.error(f'Ошибка при обновлении канала: {e}')

    # Отправка нового видео в тг
    def public_new_video(channel_name, new_video_id):
        logger.info(f'Отправка нового видео: {channel_name} - {new_video_id}')
        msg = f"На канале <b>{channel_name}</b> опубликовано <a href='https://www.youtube.com/watch?v={new_video_id}'><b><i>НОВОЕ ВИДЕО:</i></b></a> "
        bot.send_message(channel, msg, parse_mode='HTML')
        time.sleep(10)



    # Обновление клавиатуры
    def send_update_keyboard(message, message_text):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn_add = types.KeyboardButton("Добавить канал")
        btn_list = types.KeyboardButton("Список каналов")
        btn_check = types.KeyboardButton("Проверить новые публикации")
        markup.add(btn_add)
        markup.add(btn_list)
        markup.add(btn_check)
        bot.send_message(message.chat.id, message_text, reply_markup=markup)

    # Асинхроный поток для проверки базы на обновления
    schedule.every(int(check_interval)).seconds.do(check_last_video)
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(1)

    scheduler_thread = Thread(target=run_scheduler)
    scheduler_thread.start()




    if __name__ == "__main__":
        bot.polling(none_stop=True)
except Exception as e:
    logger.error(f'Ошибка при запуске бота: {e}')
