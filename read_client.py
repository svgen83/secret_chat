import asyncio
import aiofiles
import argparse
import datetime
import logging
import os

from dotenv import load_dotenv

BUFFER_SIZE = 1024

logger = logging.getLogger('chat_client')
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler('app_debug.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Клиент TCP-чата с записью логов')
    parser.add_argument(
        '--host', type=str,
        default=os.getenv('HOST'),
        help='Хост сервера чата (по умолчанию из .env)')
    parser.add_argument(
        '--port',
        type=int,
        default=os.getenv('READ_PORT'),
        help='Порт сервера чата (по умолчанию из .env)')
    parser.add_argument(
        '--log_path', type=str,
        default='chat_logs.txt',
        help='''Путь для сохранения истории переписки
        (по умолчанию: chat_logs.txt)''')
    return parser.parse_args()


async def chat_client(host, port, log_path):
    logger.info(f'Попытка подключения к {host}:{port}...')
    reader, writer = await asyncio.open_connection(host, port)
    logger.info(f'Успешно подключено к {host}:{port}')

    logger.info(f'Начало записи сообщений в файл: {log_path}')

    async with aiofiles.open(
        log_path, mode='a', encoding='utf-8') as chat_logs:
        while True:
            logger.debug('Ожидание данных от сервера...')
            data = await reader.read(BUFFER_SIZE)
            if not data:
                logger.warning(
                    'Сервер закрыл соединение (получены пустые данные).')
                break

            now = datetime.datetime.now()
            timestamp = now.strftime("%Y.%m.%d %H:%M")

            message = data.decode('utf-8', errors='replace')
            logger.info(f'Получено сообщение: {message!r}')

            await chat_logs.write(f'[{timestamp}] {message}')
            await chat_logs.flush()
            logger.debug('Сообщение записано в файл чата и буфер сброшен.')

    logger.info("Закрытие соединения...")
    writer.close()
    await writer.wait_closed()
    logger.info("Соединение закрыто.")


if __name__ == '__main__':
    load_dotenv()

    args = parse_args()
    logger.info(
        f'''Запуск клиента чата с аргументами:
            host={args.host},
            port={args.port},
            log_path={args.log_path}''')

    asyncio.run(chat_client(args.host, args.port, args.log_path))
    logger.info('Клиент чата завершен.')
