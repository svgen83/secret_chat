import anyio
import time
import logging
import gui
from gui import NicknameReceived, InvalidToken, TkAppClosed
from chat_connection import handle_connection
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def handle_outgoing_messages(send_recv, status_send, messages_send, watchdog_send, config):
    send_stream = None

    async def ensure_send_connection():
        nonlocal send_stream
        if send_stream is not None:
            return send_stream

        if not config.token:
            await status_send.send("Отправка: требуется регистрация")
            return None

        try:
            await status_send.send(gui.SendingConnectionStateChanged.INITIATED)
            send_stream = await anyio.connect_tcp(config.host, config.send_port)
            await status_send.send(gui.SendingConnectionStateChanged.ESTABLISHED)

            await send_stream.send(f"{config.token}\n".encode())
            resp_bytes = await send_stream.receive(1024)
            resp_str = resp_bytes.decode('utf-8').strip()

            if resp_str == 'null' or 'error' in resp_str.lower():
                await send_stream.aclose()
                send_stream = None
                config.token = None
                raise InvalidToken(f"Токен недействителен. Ответ сервера: {resp_str}")

            await watchdog_send.send("Send connection authorized")
            return send_stream
        except InvalidToken:
            raise
        except Exception as e:
            logger.error(f"Send connection failed: {e}")
            await watchdog_send.send(f"Send connection failed: {e}")
            if send_stream:
                try:
                    await send_stream.aclose()
                except Exception:
                    pass
            send_stream = None
            return None

    async with send_recv:
        async for user_msg in send_recv:
            try:
                stream = await ensure_send_connection()
                if stream is None:
                    continue

                try:
                    clean_msg = user_msg.replace('\n', ' ').replace('\r', ' ')
                    await stream.send(f"{clean_msg}\n\n".encode())
                    logger.info(f"Отправлено: {clean_msg[:40]}")
                    await watchdog_send.send(f"Отправлено: {clean_msg[:40]}")
                except (anyio.ClosedResourceError, anyio.BrokenResourceError, OSError) as e:
                    logger.warning(f"Потеря соединения при отправке: {e}")
                    await watchdog_send.send(f"Потеря соединения при отправке: {e}")
                    if send_stream:
                        try:
                            await send_stream.aclose()
                        except Exception:
                            pass
                    send_stream = None
                    await status_send.send("Отправка: соединение разорвано")
            except InvalidToken as e:
                logger.error(f"Ошибка авторизации: {e}")
                await watchdog_send.send(f"Ошибка авторизации: {e}")
                await status_send.send("Отправка: ошибка авторизации")
                await messages_send.send("Токен недействителен")
                config.token = None


async def watch_for_connection(watchdog_recv):
    async with watchdog_recv:
        async for event in watchdog_recv:
            logger.info(event)


async def main():
    msg_send, msg_recv = anyio.create_memory_object_stream(max_buffer_size=100)
    send_send, send_recv = anyio.create_memory_object_stream(max_buffer_size=100)
    status_send, status_recv = anyio.create_memory_object_stream(max_buffer_size=100)
    watch_send, watch_recv = anyio.create_memory_object_stream(max_buffer_size=100)

    await status_send.send(NicknameReceived(config.nickname))

    logger.info("=== Настройки чата ===")
    logger.info(f"Хост: {config.host}")
    logger.info(f"Порт чтения: {config.read_port}")
    logger.info(f"Порт отправки: {config.send_port}")
    logger.info(f"Никнейм: {config.nickname}")
    logger.info(f"Токен: {'найден' if config.token else 'не найден'}")
    logger.info("======================")

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(handle_outgoing_messages, send_recv, status_send, msg_send, watch_send, config)
            tg.start_soon(handle_connection, config.host, config.read_port, msg_send, status_send, watch_send)
            tg.start_soon(watch_for_connection, watch_recv)

            import tkinter as tk
            root = tk.Tk()
            tg.start_soon(gui.draw, root, msg_recv, status_recv, send_send)

    except BaseExceptionGroup as eg:
        expected_exits = (KeyboardInterrupt, TkAppClosed, anyio.get_cancelled_exc_class())
        real_errors = [exc for exc in eg.exceptions if not isinstance(exc, expected_exits)]

        if not real_errors:
            logger.info("Программа корректно завершена пользователем.")
        else:
            logger.error("Обнаружены ошибки в фоновых задачах:")
            for exc in real_errors:
                logger.error(f"{type(exc).__name__}: {exc}", exc_info=exc)

    except (KeyboardInterrupt, TkAppClosed):
        logger.info("Программа корректно завершена пользователем.")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("Завершение работы программы.")


if __name__ == "__main__":
    anyio.run(main)

