import asyncio
import gui
from gui import NicknameReceived
from chat_connection import read_messages, send_message
from config import config


async def handle_outgoing_messages(sending_queue, status_updates_queue):
    while True:
        user_message = await sending_queue.get()
        
        if config.token:
            await send_message(
                config.host, 
                config.send_port, 
                config.token, 
                user_message,
                status_updates_queue
            )
        else:
            status_updates_queue.put_nowait("Отправка: токен не найден")


async def main():
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    
    # Устанавливаем начальный статус
    status_updates_queue.put_nowait(NicknameReceived(config.nickname))
    
    # Выводим информацию о настройках
    print("=== Настройки чата ===")
    print(f"Хост: {config.host}")
    print(f"Порт чтения: {config.read_port}")
    print(f"Порт отправки: {config.send_port}")
    print(f"Никнейм: {config.nickname}")
    print(f"Токен: {'найден' if config.token else 'не найден'}")
    print("======================")
    
    # Запускаем все задачи
    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        read_messages(config.host, config.read_port, messages_queue, status_updates_queue),
        handle_outgoing_messages(sending_queue, status_updates_queue),
        return_exceptions=True
    )

if __name__ == "__main__":
    asyncio.run(main())
