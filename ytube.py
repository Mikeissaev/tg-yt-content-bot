from googleapiclient.discovery import build
from googleapiclient.errors import HttpError, Error
from urllib.parse import urlparse, parse_qs
import config
from loguru import logger


# Функция преобразования URL канала в идентификатор канала
def get_channel_id_by_url(url):
    try:
        channel_id = url
        parsed_url = urlparse(url)
        path = parsed_url.path.split('/')
        query = parsed_url.query
        # Проверка на стандартный URL канала
        if 'channel' in path:
            channel_id = path[path.index('channel') + 1]
            logger.info(f'Стандартный URL. ID канала: {channel_id}')
            return channel_id
        # Обработка кастомного URL канала
        elif '@' in url:
            custom_id = path[-1]  # Предполагаем, что кастомный ID находится после символа '@'
            request = youtube.search().list(q=custom_id, type='channel', part='snippet', maxResults=1)
            response = request.execute()
            if 'items' in response and len(response['items']) > 0:
                channel_id = response['items'][0]['id']['channelId']
                logger.info(f'Кастомный URL. ID канала: {channel_id}')
                return channel_id
        logger.info(f'Неизвестный URL')
        return url
    except ValueError as e:
        logger.error(f'Ошибка при анализе URL: {e}')


try:
    youtube = build('youtube', 'v3', developerKey=config.youtube_api_key)

    # Проверка существования канала
    def check_channel_exists(channel_id):
        logger.info(f'Проверка существования канала...')
        response = youtube.channels().list(
            part="snippet",
            id=channel_id,
            maxResults=1
        ).execute()
        if 'items' in response and len(response['items']) > 0:
            logger.info(f'OK')
        return 'items' in response

        
    # Получение имени канала и ID последнего видео
    def get_channel_info(channel_id):
        #logger.info('Получение имени канала и ID последнего видео ...')
        response = youtube.channels().list(
            part="snippet,contentDetails",
            id=channel_id,
            maxResults=1
        ).execute()
        channel = response['items'][0]
        channel_name = channel['snippet']['title']
        uploads_playlist_id = channel['contentDetails']['relatedPlaylists']['uploads']

        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=1 
        ).execute()

        if playlist_response['items']:
            last_video_id = playlist_response['items'][0]['snippet']['resourceId']['videoId']
            logger.info(f'Имя канала: {channel_name}, ID последнего видео: {last_video_id}')
            return channel_name, last_video_id
        else:
            logger.info(f'Имя канала: {channel_name}, видео в плейлисте не найдено.')
            return channel_name, None

except HttpError as e:
    logger.error(f'Произошла ошибка HTTP: {e.resp.status}, {e.content}')
except Error as e:
    logger.error(f'Произошла ошибка: {e}')
