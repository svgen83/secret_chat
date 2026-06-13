import anyio
import time
import gui
from gui import NicknameReceived, InvalidToken, TkAppClosed
from chat_connection import register, handle_connection
from config import config


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
        except Exception as e:
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
            stream = await ensure_send_connection()
            if stream is None:
                continue

            try:
                clean_msg = user_msg.replace('\n', ' ').replace('\r', ' ')
                await stream.send(f"{clean_msg}\n\n".encode())
                await watchdog_send.send(f"Отправлено: {clean_msg[:40]}")
            except (anyio.ClosedResourceError, anyio.BrokenResourceError, OSError) as e:
                await watchdog_send.send(f"Потеря соединения при отправке: {e}")
                if send_stream:
                    try:
                        await send_stream.aclose()
                    except Exception:
                        pass
                send_stream = None
                await status_send.send("Отправка: соединение разорвано")


async def watch_for_connection(watchdog_recv):
    async with watchdog_recv:
        async for event in watchdog_recv:
            ts = int(time.time())
            if "no activity for" in event:
                print(f"[{ts}] {event}")
            elif event.startswith('[') and ']' in event:
                print(event)
            else:
                print(f"[{ts}] Connection is alive. {event}")


async def main():
    msg_send, msg_recv = anyio.create_memory_object_stream(max_buffer_size=100)
    send_send, send_recv = anyio.create_memory_object_stream(max_buffer_size=100)
    status_send, status_recv = anyio.create_memory_object_stream(max_buffer_size=100)
    watch_send, watch_recv = anyio.create_memory_object_stream(max_buffer_size=100)
    
    await status_send.send(NicknameReceived(config.nickname))

    print("=== Настройки чата ===")
    print(f"Хост: {config.host}")
    print(f"Порт чтения: {config.read_port}")
    print(f"Порт отправки: {config.send_port}")
    print(f"Никнейм: {config.nickname}")
    print(f"Токен: {'найден' if config.token else 'не найден'}")
    print("======================")

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
            print("\n Программа корректно завершена.")
        else:
            print("\n Обнаружены ошибки в фоновых задачах:")
            for exc in real_errors:
                import traceback
                print(f"--- {type(exc).__name__}: {exc} ---")
                traceback.print_exception(type(exc), exc, exc.__traceback__)
                
    except (KeyboardInterrupt, TkAppClosed):
        print("\n Программа корректно завершена.")
    except Exception as e:
        print(f"\n Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Завершение работы программы.")


if __name__ == "__main__":
    anyio.run(main)
