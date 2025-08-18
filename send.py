 import asyncio
import json
import logging
import os

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("chat_client.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def sanitize(message):
    logger.debug(f"Sanitizing message: {repr(message)}")
    cleaned_message = message.replace("\n", " ").replace("\r", " ")
    logger.debug(f"Sanitized message: {repr(cleaned_message)}")
    return cleaned_message


async def tcp_echo_client(token, host, port, message):
    logger.info("Starting TCP client connection...")

    reader, writer = await asyncio.open_connection(host, port)
    logger.info(f"Connected to {host}:{port}")

    welcome_data = await reader.readline()
    welcome_msg = welcome_data.decode()
    logger.info(f"Server Welcome: {welcome_msg!r}")

    auth_message = f'{token}\n'
    logger.info(f"Sending authentication token: {auth_message!r}")
    writer.write(auth_message.encode())
    await writer.drain()
    logger.debug("Authentication token sent.")

    auth_response_data = await reader.readline()
    auth_response_json = json.loads(auth_response_data)
    if auth_response_json is None: 
        logger.warning("Invalid token")
        writer.close()
        await writer.wait_closed()
        logger.info("Connection closed.")
        logger.info("TCP client finished.")
    else:
        auth_response = auth_response_data.decode()
        logger.info(f"Authentication Response: {auth_response!r}")
        sanitized_message = sanitize(message)

        chat_message = f"{sanitized_message}\n\n"
        logger.info(f"Sending chat message: {repr(chat_message)}")
        writer.write(chat_message.encode())
        await writer.drain()
        logger.debug("Chat message sent.")

        logger.info("Reading server responses for a short period...")
        data = await reader.read(1024)
        logger.info(f'Received: {data.decode()!r}')
        logger.info("Finished reading server responses.")
        writer.close()
        await writer.wait_closed()

        logger.info("Connection closed.")
        logger.info("TCP client finished.")


if __name__ == "__main__":
    load_dotenv()

    token = os.getenv('TOKEN')
    port = os.getenv('SEND_PORT')
    host = os.getenv('HOST')
    asyncio.run(tcp_echo_client(token, host, port, 'Тест чата'))
