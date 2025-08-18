import asyncio
import json
import argparse
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("registration.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def register_user(host, port, nickname, token_file):
    logger.info(f"Начало регистрации пользователя '{nickname}' на {host}:{port}...")

    reader, writer = await asyncio.open_connection(host, port)
    logger.info("Подключение к серверу установлено.")

    welcome_data = await reader.readline()
    welcome_msg = welcome_data.decode()
    logger.info(f"Получено приветствие: {welcome_msg!r}")
    print(welcome_msg, end='')

    logger.info("Отправка пустой строки для инициации регистрации...")
    writer.write(b'\n') # Отправляем просто символ новой строки
    await writer.drain()

    nickname_prompt_data = await reader.readline()
    nickname_prompt = nickname_prompt_data.decode()
    logger.info(f"Запрос никнейма: {nickname_prompt!r}")
    print(nickname_prompt, end='')

    nickname_message = f"{nickname}\n"
    logger.info(f"Отправка никнейма: {nickname_message!r}")
    writer.write(nickname_message.encode())
    await writer.drain()

    confirmation_data = await reader.readline()
    confirmation_msg = confirmation_data.decode()
    logger.info(f"Получено подтверждение регистрации: {confirmation_msg!r}")
    print(confirmation_msg, end='') # Показываем пользователю

    # --- Шаг 6: Парсинг JSON для извлечения нового account_hash ---
    confirmation_json = json.loads(confirmation_msg)
    new_account_hash = confirmation_json.get("account_hash")

    if new_account_hash:
        logger.info(f"Новый account_hash получен: {new_account_hash}")
        with open(token_file, 'w', encoding='utf-8') as f:
            f.write(new_account_hash)
        logger.info(f"Новый токен сохранен в файл '{token_file}'.")
        print(f"\nРегистрация успешна! Ваш токен сохранен в файл '{token_file}'.")
        print(f"Используйте его для отправки сообщений.")
    else:
        logger.error("Новый account_hash не найден в ответе сервера.")
        print("\nОшибка: Не удалось получить новый токен из ответа сервера.")

    logger.info("Закрытие соединения...")
    writer.close()
    await writer.wait_closed()
    logger.info("Соединение закрыто.")

def main():
    parser = argparse.ArgumentParser(description="Регистрация нового пользователя в чате.")
    parser.add_argument('--host', type=str, default='minechat.dvmn.org',
                        help='Хост сервера чата (по умолчанию: minechat.dvmn.org)')
    parser.add_argument('--port', type=int, default=5050,
                        help='Порт сервера чата (по умолчанию: 5050)')
    parser.add_argument('--nickname', type=str, required=True,
                        help='Желаемый никнейм')
    parser.add_argument('--token_file', type=str, default='token.txt',
                        help='Файл для сохранения нового токена (по умолчанию: token.txt)')

    args = parser.parse_args()

    asyncio.run(register_user(args.host, args.port, args.nickname, args.token_file))

if __name__ == '__main__':
    main()