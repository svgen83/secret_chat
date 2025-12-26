import asyncio
import gui
import time

from gui import NicknameReceived, InvalidToken
from chat_connection import read_messages, send_message,create_connection
from chat_connection import history_manager, register
from config import config
from tkinter import messagebox


async def handle_outgoing_messages(sending_queue,
                                   status_updates_queue,
                                   messages_queue,
                                   watchdog_queue):
    reader = None
    writer = None

    while True:
        user_message = await sending_queue.get()

        if not config.token:
            status_updates_queue.put_nowait("Отправка: регистрация...")
            print("Токен не найден, начинаем регистрацию...")
            watchdog_queue.put_nowait("Registration started")
                
            # Создаем соединение для регистрации
            reader, writer = await asyncio.open_connection(config.host, config.send_port)
            watchdog_queue.put_nowait("Prompt before auth")
            new_token = await register(reader, writer, config.nickname, config.token_path)
            print(new_token)
            if new_token:
                config.token = new_token
                status_updates_queue.put_nowait("новый токен")
                messages_queue.put_nowait(
                    f"Зарегистрирован новый пользователь: {config.nickname}")
                watchdog_queue.put_nowait("Registration complete")
            else:
                status_updates_queue.put_nowait("Отправка: ошибка регистрации")
                messages_queue.put_nowait("Ошибка регистрации. Попробуйте еще раз.")
                print("Ошибка регистрации")
                watchdog_queue.put_nowait("Registration complete")
       
        # Если соединение не установлено - создаем его
        if not writer:
            reader, writer = await create_connection(
                config.host, 
                config.send_port, 
                config.token, 
                status_updates_queue,
                watchdog_queue
                )
        
        if writer:
            await send_message(reader, writer,
                               user_message,
                               status_updates_queue,
                               watchdog_queue)


async def watch_for_connection(watchdog_queue):
    print("Watchdog запущен")
    while True:
        event = await watchdog_queue.get()
        
        timestamp = int(time.time())

        print(f"[{timestamp}] Connection is alive. {event}")


async def main():
    messages_queue = asyncio.Queue()
    sending_queue = asyncio.Queue()
    status_updates_queue = asyncio.Queue()
    watchdog_queue = asyncio.Queue()
    
    status_updates_queue.put_nowait(NicknameReceived(config.nickname))
    
    # Вывод информации о настройках
    print("=== Настройки чата ===")
    print(f"Хост: {config.host}")
    print(f"Порт чтения: {config.read_port}")
    print(f"Порт отправки: {config.send_port}")
    print(f"Никнейм: {config.nickname}")
    print(f"Токен: {'найден' if config.token else 'не найден'}")
    print("======================")
    
    try:
        await asyncio.gather(
            gui.draw(messages_queue, sending_queue, status_updates_queue),
            read_messages(config.host, config.read_port, messages_queue, status_updates_queue, watchdog_queue),
            handle_outgoing_messages(sending_queue, status_updates_queue, messages_queue, watchdog_queue),
            history_manager(messages_queue, 'chat_history.txt'),
            watch_for_connection(watchdog_queue)
            )
    except InvalidToken as e:
        print(f"Ошибка авторизации: {e}")
        e.show_error_dialog()
        root.destroy()
        print(f"Ошибка: {e}")
    except gui.TkAppClosed:
        print("Приложение закрыто")
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        print("Программа завершена")

if __name__ == "__main__":
    asyncio.run(main())
