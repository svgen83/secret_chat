import asyncio
import json
from datetime import datetime
from config import config


async def read_messages(host, port, messages_queue, status_updates_queue):
    while True:
        try:
            status_updates_queue.put_nowait("Чтение: устанавливаем соединение")
            reader, writer = await asyncio.open_connection(host, port)
            status_updates_queue.put_nowait("Чтение: соединение установлено")
            while True:
                data = await reader.read(1024)
                if not data:
                    break  
                message = data.decode('utf-8').strip()
                if message:
                    timestamp = datetime.now().strftime("%H:%M")
                    formatted_message = f"[{timestamp}] {message}"
                    messages_queue.put_nowait(formatted_message)
        except:
            status_updates_queue.put_nowait("Чтение: соединение закрыто")
            await asyncio.sleep(5)
            continue
        
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass


async def authorize(reader, writer, token):
    """Авторизация по токену"""
    try:
        # Читаем приветственное сообщение
        await reader.readline()
        
        # Отправляем токен
        auth_message = f"{token}\n"
        writer.write(auth_message.encode())
        await writer.drain()
        
        # Читаем ответ авторизации
        auth_response = await reader.readline()
        return auth_response.decode().strip() != "null"
            
    except:
        return False


async def send_message(host, port, token, message, status_updates_queue):
    """Отправка сообщения в чат"""
    try:
        status_updates_queue.put_nowait("Отправка: устанавливаем соединение")
        
        reader, writer = await asyncio.open_connection(host, port)
        status_updates_queue.put_nowait("Отправка: соединение установлено")
        
        # Авторизуемся
        if not await authorize(reader, writer, token):
            status_updates_queue.put_nowait("Отправка: ошибка авторизации")
            return False
        
        # Очищаем и отправляем сообщение
        clean_message = message.replace("\n", " ").replace("\r", " ")
        message_to_send = f"{clean_message}\n\n"
        writer.write(message_to_send.encode())
        await writer.drain()
        
        # Читаем ответ
        await reader.read(1024)
        return True
        
    except:
        status_updates_queue.put_nowait("Отправка: ошибка соединения")
        return False
        
    finally:
        try:
            writer.close()
            await writer.wait_closed()
            status_updates_queue.put_nowait("Отправка: соединение закрыто")
        except:
            pass
