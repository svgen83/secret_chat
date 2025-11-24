import os
import argparse
from dotenv import load_dotenv


def load_config():
    load_dotenv()  
    
    parser = argparse.ArgumentParser(description='GUI клиент для чата')
    parser.add_argument(
        '--host',
        type=str,
        default=os.getenv('HOST', 'minechat.dvmn.org'),
        help='Хост сервера чата'
    )
    parser.add_argument(
        '--read_port',
        type=int,
        default=int(os.getenv('READ_PORT', 5000)),
        help='Порт для чтения сообщений'
    )
    parser.add_argument(
        '--send_port', 
        type=int,
        default=int(os.getenv('SEND_PORT', 5050)),
        help='Порт для отправки сообщений'
    )
    parser.add_argument(
        '--token',
        type=str,
        default=os.getenv('TOKEN'),
        help='Токен пользователя'
    )
    parser.add_argument(
        '--token_path',
        type=str,
        default='token_file.txt',
        help='Путь к файлу с токеном'
    )
    parser.add_argument(
        '--nickname',
        type=str,
        default=os.getenv('NICKNAME', 'Аноним'),
        help='Никнейм пользователя'
    )
    
    args = parser.parse_args()
    
    # Если токен не передан, пробуем загрузить из файла
    if not args.token and os.path.exists(args.token_path):
        try:
            with open(args.token_path, 'r', encoding='utf-8') as f:
                args.token = f.read().strip()
        except Exception as e:
            print(f"Ошибка чтения токена из файла: {e}")
    
    return args


# переменная для хранения конфигурации
config = load_config()
