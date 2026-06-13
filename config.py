import os
import argparse
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def load_config():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='GUI клиент для чата')
    parser.add_argument('--host', type=str, default=os.getenv(
        'HOST', 'minechat.dvmn.org'), help='Хост сервера чата')
    parser.add_argument('--read_port', type=int, default=int(os.getenv(
        'READ_PORT', 5000)), help='Порт для чтения')
    parser.add_argument('--send_port', type=int, default=int(os.getenv(
        'SEND_PORT', 5050)), help='Порт для отправки')
    parser.add_argument('--token', type=str, default=os.getenv(
        'TOKEN'), help='Токен пользователя')
    parser.add_argument('--token_path', type=str, default='token_file.txt', help='Путь к файлу с токеном')
    parser.add_argument('--nickname', type=str, default=os.getenv('NICKNAME', 'Аноним'), help='Никнейм')
    
    args = parser.parse_args()
    
    if not args.token and os.path.exists(args.token_path):
        try:
            with open(args.token_path, 'r', encoding='utf-8') as f:
                lines = f.read().strip().split('\n')
                if len(lines) >= 1:
                    args.token = lines[0].strip()
                if len(lines) >= 2:
                    args.nickname = lines[1].strip()
        except Exception as e:
            logger.error(f"Ошибка чтения файла учётных данных: {e}")
    
    return args

config = load_config()
