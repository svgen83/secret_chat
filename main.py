import asyncio
import aiofiles
import datetime


def parse_args():
    parser = argparse.ArgumentParser(description="Клиент TCP-чата с записью логов")
    parser.add_argument('--host', type=str, default='minechat.dvmn.org',
                        help='Хост сервера чата (по умолчанию: minechat.dvmn.org)')
    parser.add_argument('--port', type=int, default=5000,
                        help='Порт сервера чата (по умолчанию: 5000)')
    parser.add_argument('--history', type=str, default='chat_logs.txt',
                        help='Путь для сохранения истории переписки (по умолчанию: chat_logs.txt)')
    return parser.parse_args()


async def chat_client(host, port, log_path):
    while True:
        reader, writer = await asyncio.open_connection(
        host, port)
        async with aiofiles.open(log_path, mode='a') as chat_logs:
            while True:
                data = await reader.read(100)
                now = datetime.datetime.now()
                timestamp = now.strftime("%Y.%m.%d %H:%M")
                
                message = data.decode('utf-8', errors='ignore')
                print(message)
                await asyncio.sleep(1)
                await chat_logs.write(f"[{timestamp}] {message}\n")
                await chat_logs.flush()
        writer.close()
        await writer.wait_closed()
        print("Соединение закрыто.")


if __name__ == '__main__':
    args = parse_args()
    asyncio.run(chat_client())

