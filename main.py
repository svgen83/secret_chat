import asyncio
import aiofiles
import datetime


HOST='minechat.dvmn.org'
PORT=5000

async def chat_client():
    while True:
        reader, writer = await asyncio.open_connection(
        HOST, PORT)
        #print('Есть контакт')
        #writer.write(message.encode())
        #await writer.drain()
        #writer.write(data.decode())
        #await writer.drain()

        async with aiofiles.open('chat_logs.txt', mode='a') as chat_logs:
            while True:
                data = await reader.read(100)
                now = datetime.datetime.now()
                timestamp = now.strftime("%Y.%m.%d %H:%M")
                message = data.decode('utf-8', errors='ignore')
                print(message)
                await chat_logs.write(message)


        #print('Close the connection')
        #writer.close()
        #await writer.wait_closed()


if __name__ == '__main__':
    asyncio.run(chat_client())
