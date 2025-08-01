import asyncio
import json


token = ''

def sanitize(message):
    return message.replace("\n", "").replace("\r", "")


async def tcp_echo_client(token, message):
    reader, writer = await asyncio.open_connection(
        'minechat.dvmn.org', 5050)
    
    welcome_data = await reader.readline()
    print(f'Server Welcome: {welcome_data.decode()!r}')
        
    auth_message = token + '\n'
    print(f'Sending auth: {auth_message!r}')
    writer.write(auth_message.encode())
    await writer.drain()
    
    data = await reader.readline()
    print(f'Received: {data.decode()!r}')
        
    chat_message = "{}\n\n".format(sanitize(message))
    print(f'Sending message: {chat_message!r}')
    writer.write(chat_message.encode())
    await writer.drain()
    
    # Получение ответа
    data = await reader.read(1024)
    print(f'Received: {data.decode()!r}')
    
    writer.close()
    await writer.wait_closed()
    print("-" * 20 + "\n")

asyncio.run(tcp_echo_client(token, 'Тест чата'))
