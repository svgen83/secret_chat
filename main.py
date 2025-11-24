import asyncio
import gui
from gui import ReadConnectionStateChanged, SendingConnectionStateChanged, NicknameReceived
from datetime import datetime

async def display_test_messages(messages_queue, status_updates_queue):
    status_updates_queue.put_nowait(NicknameReceived("Тестовый_Пользователь"))
    status_updates_queue.put_nowait(ReadConnectionStateChanged.ESTABLISHED)
    status_updates_queue.put_nowait(SendingConnectionStateChanged.ESTABLISHED)
    while True:
        await asyncio.sleep(1)         
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = f"{timestamp}"
        messages_queue.put_nowait(message)

async def main():
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()   
    await asyncio.gather(
        gui.draw(messages_queue, sending_queue, status_updates_queue),
        display_test_messages(messages_queue, status_updates_queue),
        return_exceptions=True
    )

if __name__ == "__main__":
    asyncio.run(main())
