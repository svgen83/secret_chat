import aiofiles
import asyncio
import json
import gui
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
    while True:
        status_updates_queue.put_nowait(gui.ReadConnectionStateChanged.INITIATED)
        try:
            watchdog_queue.put_nowait("Read connection: establishing")
            status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.INITIATED)
            reader, writer = await asyncio.open_connection(host, port)
            status_updates_queue.put_nowait(gui.SendingConnectionStateChanged.ESTABLISHED)
            watchdog_queue.put_nowait("Read connection: established")
            while True:
                data = await reader.read(1024)
                if not data:
                    break  
                message = data.decode('utf-8').strip()
                if message:
                    timestamp = datetime.now().strftime("%H:%M")
                    formatted_message = f"[{timestamp}] {message}"
                    messages_queue.put_nowait(formatted_message)
                    watchdog_queue.put_nowait("New message in chat")
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
