import aiofiles
import asyncio
import json
import gui
import time
from async_timeout import timeout

from datetime import datetime
from config import config


async def create_connection(host, port, token, status_updates_queue, watchdog_queue):
    status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.INITIATED)
    watchdog_queue.put_nowait("Send connection: establishing")
    reader, writer = await asyncio.open_connection(host, port)
    status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)
    watchdog_queue.put_nowait("Send connection: establishing")

    watchdog_queue.put_nowait("Prompt before auth")
    welcome_message = await reader.readline()
    
    # Авторизуемся
    watchdog_queue.put_nowait("Authorization request")
    auth_message = f"{token}\n"
    writer.write(auth_message.encode())
    await writer.drain()
    
    auth_response = await reader.readline()
    if auth_response.decode().strip() == "null":
        status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.CLOSED)
        writer.close()
        await writer.wait_closed()
        raise gui.InvalidToken("Неверный токен авторизации")
    
    status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.CLOSED)
    watchdog_queue.put_nowait("Authorization done")
    return reader, writer


async def register(reader, writer, nickname, token_path, watchdog_queue):

    hello_message = await reader.readline()
    writer.write(b'\n')
    await writer.drain()

    nickname_prompt_data = await reader.readline()
    nickname_prompt = nickname_prompt_data.decode()

    nickname_message = f"{nickname}\n"
    print(f"Отправка никнейма: {nickname_message!r}")
    writer.write(nickname_message.encode())
    await writer.drain()

    confirmation_data = await reader.readline()
    confirmation_msg = confirmation_data.decode()

    try:
        confirmation_json = json.loads(confirmation_msg)
        new_token = confirmation_json.get("account_hash")
        server_nickname = confirmation_json.get("nickname", nickname)

        if new_token and server_nickname:
            with open(token_path, 'w', encoding='utf-8') as file:
                file.write(new_token)
            print(f"Новый токен сохранен в файл '{token_path}'.")
            return new_token, server_nickname
        else:
            return None, None
    except json.JSONDecodeError:
        logger.error(
            f"Ответ сервера не является корректным JSON: {confirmation_msg!r}")
        return None, None
    

async def send_message(reader, writer, message, status_updates_queue, watchdog_queue):
    clean_message = message.replace("\n", " ").replace("\r", " ")
    message_to_send = f"{clean_message}\n\n"
    watchdog_queue.put_nowait(f"Message: {clean_message[:50]}")
    writer.write(message_to_send.encode())
    await writer.drain()
    await reader.read(1024)
    return True


async def load_chat_history(messages_queue, log_path):
    try:
        async with aiofiles.open(log_path, 'r', encoding='utf-8') as chat_logs:
            async for line in chat_logs:
                message = line.strip()
                if message:
                    messages_queue.put_nowait(message)
    except FileNotFoundError:
        pass


async def save_message_to_history(message, log_path):
    try:
        async with aiofiles.open(log_path, 'a', encoding='utf-8') as chat_logs:
            await chat_logs.write(f"{message}\n")
    except Exception:
        pass


async def history_manager(messages_queue, log_path):
    await load_chat_history(messages_queue, log_path)
    while True:
        message = await messages_queue.get()
        await save_message_to_history(message, log_path)


async def handle_connection_0(host, port, messages_queue, status_updates_queue, watchdog_queue):
    SILENCE_TIMEOUT = 5  # Допустимое молчание сервера (сек)
    PING_INTERVAL = 30   # Интервал отправки пингов (сек)

    while True:  
        try:
            status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)
            watchdog_queue.put_nowait("Connection: attempting to connect")
            
            reader, writer = await asyncio.open_connection(host, port)
            status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.ESTABLISHED)
            watchdog_queue.put_nowait("Connection: established")
            
            ping_task = asyncio.create_task(
                ping_pong(writer, watchdog_queue, PING_INTERVAL))
            
            try:
                last_message_time = time.time()
                
                while True:
                    try:
                        async with timeout(1.0):
                            data = await reader.read(1024)
                            
                        if data:
                            last_message_time = time.time()
                            message = data.decode('utf-8').strip()
                            if message:
                                timestamp = time.strftime("%H:%M")
                                formatted_message = f"[{timestamp}] {message}"
                                messages_queue.put_nowait(formatted_message)
                                watchdog_queue.put_nowait("New message in chat")
                        else:
                            watchdog_queue.put_nowait("Connection: server closed stream")
                            break
                            
                    except asyncio.TimeoutError:
                        current_time = time.time()
                        silence_duration = int(current_time - last_message_time)
                        
                        if silence_duration > SILENCE_TIMEOUT:
                            watchdog_queue.put_nowait(
                                f"Connection: no activity for {silence_duration}s")
                            break 
                            
            finally:
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass
                    
                status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.CLOSED)
                writer.close()
                await writer.wait_closed()
                
        except Exception as e:
            print(f"Ошибка соединения: {e}")
            watchdog_queue.put_nowait(f"Connection error: {e}")
        
        await asyncio.sleep(2)


async def ping_pong(writer, watchdog_queue, interval=30):
    while True:
        await asyncio.sleep(interval)
        try:
            async with timeout(5.0):
                watchdog_queue.put_nowait("Sending ping...")
                writer.write(b"ping\n") 
                await writer.drain()
            watchdog_queue.put_nowait("Ping sent successfully")
            
        except asyncio.TimeoutError:
            watchdog_queue.put_nowait("⏳ Ping timeout! Connection likely dead.")
            break
        except Exception as e:
            watchdog_queue.put_nowait(f"Ping error: {e}")
            break
            

async def handle_connection(
    host, port, messages_queue, status_updates_queue,
    watchdog_queue):
    SILENCE_TIMEOUT = 5   # Макс. время молчания сервера (сек)
    PING_INTERVAL = 30    # Интервал отправки пингов (сек)

    while True:
        try:
            status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)
            watchdog_queue.put_nowait("Connection: attempting to connect")

            reader, writer = await asyncio.open_connection(host, port)

            status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.ESTABLISHED)
            watchdog_queue.put_nowait("Connection: established")

            ping_task = asyncio.create_task(ping_pong(writer, watchdog_queue, PING_INTERVAL))

            last_message_time = time.time()

            try:
                while True:
                    try:
                        # 🔹 Используем async_timeout для чтения
                        async with timeout(1.0) as cm:
                            data = await reader.read(1024)

                        # Если данные получены успешно
                        if not data:
                            watchdog_queue.put_nowait("Server closed connection stream")
                            break

                        message = data.decode('utf-8').strip()
                        if message:
                            last_message_time = time.time()
                            timestamp = time.strftime("%H:%M")
                            messages_queue.put_nowait(f"[{timestamp}] {message}")
                            watchdog_queue.put_nowait("New message in chat")

                    except asyncio.TimeoutError:
                        # ⏱️ Сюда попадаем при истечении времени ожидания read()
                        if cm.expired:  # ✅ Ваша явная проверка
                            current_time = int(time.time())
                            watchdog_queue.put_nowait(f"[{current_time}] 1.0s read timeout elapsed")

                        # Проверяем общее молчание сервера
                        if time.time() - last_message_time > SILENCE_TIMEOUT:
                            watchdog_queue.put_nowait(f"Connection: no activity for {SILENCE_TIMEOUT}s")
                            break  # Выходим из цикла чтения → соединение будет закрыто и пересоздано
                            
            finally:
                # 🛑 Гарантированно останавливаем фоновую пинг-задачу
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass

                status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.CLOSED)
                writer.close()
                await writer.wait_closed()

        except Exception as e:
            print(f"Ошибка соединения: {e}")
            watchdog_queue.put_nowait(f"Connection error: {e}")
            status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.CLOSED)

        # Пауза перед попыткой переподключения
        await asyncio.sleep(2)

