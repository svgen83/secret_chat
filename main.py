import asyncio
import gui
from gui import ReadConnectionStateChanged, SendingConnectionStateChanged, NicknameReceived
from datetime import datetime
from config import config  

async def display_test_messages(messages_queue, status_updates_queue):
    
    status_updates_queue.put_nowait(NicknameReceived(config.nickname))
    status_updates_queue.put_nowait(ReadConnectionStateChanged.ESTABLISHED)
    status_updates_queue.put_nowait(SendingConnectionStateChanged.ESTABLISHED)
    
    messages_queue.put_nowait(f"Подключение к: {config.host}:{config.read_port} (чтение)")
    messages_queue.put_nowait(f"Подключение к: {config.host}:{config.send_port} (отправка)")
    messages_queue.put_nowait(f"Никнейм: {config.nickname}")
    
    if config.token:
        messages_queue.put_nowait("Токен: найден")
    else:
        messages_queue.put_nowait("Токен: не найден (требуется регистрация)")
    
    # Генерация тестовых сообщений
    counter = 0
    while True:
        await asyncio.sleep(2)  # Сообщение каждые 2 секунды
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        counter += 1
        message = f"[{timestamp}] Тестовое сообщение #{counter} от {config.nickname}"
        messages_queue.put_nowait(message)

async def main():
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    
    print("=== Настройки чата ===")
    print(f"Хост: {config.host}")
    print(f"Порт чтения: {config.read_port}")
    print(f"Порт отправки: {config.send_port}")
    print(f"Никнейм: {config.nickname}")
    print(f"Токен: {'найден' if config.token else 'не найден'}")
    print("======================")
    
    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        display_test_messages(messages_queue, status_updates_queue),
        return_exceptions=True
    )

if __name__ == "__main__":
    asyncio.run(main())
