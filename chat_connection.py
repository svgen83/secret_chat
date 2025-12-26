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


async def read_messages(host, port, messages_queue, status_updates_queue, watchdog_queue):
    timeout_seconds = 1
    
    while True:
        status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)
        try:
            watchdog_queue.put_nowait("Read connection: establishing")
            status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.INITIATED)
            reader, writer = await asyncio.open_connection(host, port)
            status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)
            watchdog_queue.put_nowait("Read connection: established")
            while True:
                async with timeout(timeout_seconds) as cm:
                    data = await reader.read(1024)
                if not data:
                    break  
                message = data.decode('utf-8').strip()
                if message:
                    timestamp = datetime.now().strftime("%H:%M")
                    formatted_message = f"[{timestamp}] {message}"
                    messages_queue.put_nowait(formatted_message)
                    watchdog_queue.put_nowait("New message in chat")
                if cm.expired:
                    current_time = int(time.time())
                    watchdog_queue.put_nowait(f"[{current_time}] {timeout_seconds}s timeout is elapsed")
        except:
            status_updates_queue.put_nowait("Чтение: соединение закрыто")
            watchdog_queue.put_nowait("Read connection: error") 
            await asyncio.sleep(1)
            continue   
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass


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
        if new_token:
            with open(token_path, 'w', encoding='utf-8') as file:
                file.write(new_token)
            print(f"Новый токен сохранен в файл '{token_path}'.")
            return new_token
        else:
            return None
    except json.JSONDecodeError:
        logger.error(
            f"Ответ сервера не является корректным JSON: {confirmation_msg!r}")
        return None
    finally:
        writer.close()
        await writer.wait_closed()


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


async def handle_connection(host, port, messages_queue, status_updates_queue, watchdog_queue):
   
    SILENCE_TIMEOUT = 5  # Разрывать соединение после 5 секунд молчания
    
    while True:  
        try:
            print(f"Подключаемся к {host}:{port}")
            watchdog_queue.put_nowait("Connection: attempting to connect")
            
            # Подключаемся
            reader, writer = await asyncio.open_connection(host, port)
            watchdog_queue.put_nowait("Connection: established")
            watchdog_queue.put_nowait("Prompt before auth")
            
           
            last_message_time = time.time()
            
            try:
                while True:
                    try:
                        
                        data = await asyncio.wait_for(reader.read(1024), timeout=1.0)
                        
                        if data:
                           
                            last_message_time = time.time()
                            
                            message = data.decode('utf-8').strip()
                            if message:
                                timestamp = time.strftime("%H:%M")
                                formatted_message = f"[{timestamp}] {message}"
                                messages_queue.put_nowait(formatted_message)
                                watchdog_queue.put_nowait("New message in chat")
                        else:
                            
                            break
                            
                    except asyncio.TimeoutError:
                        
                        current_time = time.time()
                        silence_duration = int(current_time - last_message_time)

                        timestamp = int(current_time)
                        print(f"[{timestamp}] {silence_duration}s timeout is elapsed")
                        
    
                        if silence_duration > SILENCE_TIMEOUT:
                            print(f"[{timestamp}] Server silent for {silence_duration}s, closing connection")
                            watchdog_queue.put_nowait(f"Connection: no activity for {silence_duration}s")
                            break
                            
            finally:
                writer.close()
                await writer.wait_closed()
                
        except Exception as e:
            print(f"Ошибка: {e}")
            watchdog_queue.put_nowait(f"Connection error: {e}")
        
        await asyncio.sleep(2)
