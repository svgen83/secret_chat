import asyncio
import json
import logging
import os
import argparse

from dotenv import load_dotenv

BUFFER_SIZE = 1024

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("chat_client.log", encoding='utf-8'),
        logging.StreamHandler()])
logger = logging.getLogger(__name__)


def sanitize(message):
    logger.debug(f"Очистка сообщения: {repr(message)}")
    cleaned_message = message.replace("\n", " ").replace("\r", " ")
    logger.debug(f"Очищенное сообщение: {repr(cleaned_message)}")
    return cleaned_message


async def register(reader, writer, nickname, token_path):
    logger.info("Начало регистрации пользователя...")

    logger.info("Ожидание запроса никнейма...")
    nickname_prompt_data = await reader.readline()
    nickname_prompt = nickname_prompt_data.decode()
    logger.info(f"Запрос никнейма: {nickname_prompt!r}")

    nickname_message = f"{nickname}\n"
    logger.info(f"Отправка никнейма: {nickname_message!r}")
    writer.write(nickname_message.encode())
    await writer.drain()

    confirmation_data = await reader.readline()
    confirmation_msg = confirmation_data.decode()
    logger.info(f"Получено подтверждение регистрации: {confirmation_msg!r}")

    try:
        confirmation_json = json.loads(confirmation_msg)
        new_token = confirmation_json.get("account_hash")

        if new_token:
            logger.info(f"Новый токен получен: {new_token}")
            with open(token_path, 'w', encoding='utf-8') as file:
                file.write(new_token)
            logger.info(f"Новый токен сохранен в файл '{token_path}'.")
            return new_token
        else:
            logger.error("Новый токен не найден в ответе сервера.")
            return None
    except json.JSONDecodeError:
        logger.error(
            f"Ответ сервера не является корректным JSON: {confirmation_msg!r}")
        return None

    finally:
        logger.info("Закрытие соединения...")
        writer.close()
        await writer.wait_closed()
        logger.info("Соединение закрыто.")


async def authorise(reader, writer, token):
    logger.info("Начало авторизации...")

    welcome_data = await reader.readline()
    welcome_msg = welcome_data.decode()
    logger.info(f"Приветственое сообщение: {welcome_msg!r}")

    auth_message = f'{token}\n'
    logger.info(f"Аутентификация по токену: {auth_message!r}")
    writer.write(auth_message.encode())
    await writer.drain()
    logger.debug("Токен успешно отправлен")

    auth_response_data = await reader.readline()
    auth_response_raw = auth_response_data.decode()
    logger.info(f"Необработанный ответ аутентификации: {auth_response_raw!r}")

    if auth_response_raw.strip() == 'null':
        logger.warning(
            "Ошибка: Сервер вернул 'null'. Возможно, токен недействителен")
        return False
    else:
        logger.info(f"Успешная авторизация: {auth_response_raw!r}")
        return True


async def submit_message(reader, writer, message):
    logger.info("Начало отправки сообщения...")

    sanitized_message = sanitize(message)
    chat_message = f"{sanitized_message}\n\n"
    logger.info(f"Отправка сообщения в чат: {repr(chat_message)}")

    writer.write(chat_message.encode())
    await writer.drain()
    logger.info("Сообщение отправлено")

    logger.info("Чтение ответа сервера")
    data = await reader.read(BUFFER_SIZE)
    response = data.decode()
    logger.info(f'Получен ответ от сервера: {response!r}')


async def tcp_client(host, port, token, token_path, nickname, message):
    logger.info("Запуск соединения...")

    reader, writer = await asyncio.open_connection(host, port)
    logger.info(f"Подключено к {host}:{port}")

    is_authorized = await authorise(reader, writer, token)

    if is_authorized:
        welcome_data = await reader.readline()
        logger.info(
            f'Приветственное сообщение: {welcome_data.decode()!r}')
        await submit_message(reader, writer, message)
    else:
        await register(reader, writer, nickname, token_path)
        logger.info("Авторизация не удалась.")

    logger.info("Закрытие соединения...")
    writer.close()
    await writer.wait_closed()
    logger.info("Соединение закрыто")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Клиент чата: регистрация и отправка сообщений.")
    parser.add_argument(
        '--host',
        type=str,
        default=os.getenv('HOST'),
        help='Хост сервера чата (по умолчанию из .env)')
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.getenv('SEND_PORT')),
        help='Порт сервера чата (по умолчанию из .env)')
    parser.add_argument(
        '--token',
        type=str,
        default=os.getenv('TOKEN'),
        help='Токен (по умолчанию из .env)')
    parser.add_argument(
        '--token_path',
        type=str,
        default='token_file.txt',
        help='при новой регистрации токен сохраняется в token_file.txt')
    parser.add_argument(
        '--nickname',
        type=str,
        help='Никнейм для регистрации')
    parser.add_argument(
        '--message',
        type=str,
        default='Тестовое сообщение',
        help='''Сообщение для отправки в чат (
            по умолчанию: "Тестовое сообщение")''')
    return parser.parse_args()


if __name__ == "__main__":
    load_dotenv()

    args = parse_args()

    logger.info(
        f'''Запуск клиента чата с аргументами:
        host={args.host}, port={args.port},
        token={args.token if args.token else 'None'},
        nickname={args.nickname if args.nickname else 'None'}''')

    asyncio.run(tcp_client(
        args.host, args.port,
        args.token, args.token_path,
        args.nickname, args.message))
    logger.info("Клиент чата завершен.")
