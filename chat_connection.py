import asyncio
import anyio
import json
import time
import gui

async def ping_pong(stream, watchdog_send, interval=30):
    while True:
        await anyio.sleep(interval)
        try:
            await asyncio.wait_for(stream.send(b"ping\n"), timeout=5.0)
            await watchdog_send.send("Ping OK")
        except asyncio.TimeoutError:
            await watchdog_send.send("Ping timeout! Connection likely dead.")
            break
        except anyio.get_cancelled_exc_class():
            break
        except Exception as e:
            await watchdog_send.send(f"Ping error: {e}")
            break

async def register(stream, nickname, token_path, watchdog_send):
    await stream.receive_until(b'\n', 1024)
    await stream.send(b'\n')
    await stream.receive_until(b'\n', 1024)
    await stream.send(f"{nickname}\n".encode())

    resp_line = await stream.receive_until(b'\n', 1024)
    resp_str = resp_line.decode().strip()
    
    try:
        data = json.loads(resp_str)
        token = data.get("account_hash")
        nick = data.get("nickname", nickname)
        if token:
            with open(token_path, 'w', encoding='utf-8') as f:
                f.write(token)
            return token, nick
        return None, None
    except Exception:
        return None, None

async def handle_connection(host, port, messages_send, status_send, watchdog_send):
    SILENCE_TIMEOUT = 5
    PING_INTERVAL = 30

    while True:
        try:
            await status_send.send(gui.ReadConnectionStateChanged.INITIATED)
            await watchdog_send.send("Connection: attempting to connect")

            async with await anyio.connect_tcp(host, port) as stream:
                await status_send.send(gui.ReadConnectionStateChanged.ESTABLISHED)
                await watchdog_send.send("Connection: established")

                async with anyio.create_task_group() as ping_tg:
                    ping_tg.start_soon(ping_pong, stream, watchdog_send, PING_INTERVAL)

                    last_msg_time = time.time()
                    try:
                        while True:
                            try:
                                data = await asyncio.wait_for(stream.receive(1024), timeout=1.0)
                            except asyncio.TimeoutError:
                                await watchdog_send.send(f"[{int(time.time())}] Read timeout")
                                if time.time() - last_msg_time > SILENCE_TIMEOUT:
                                    await watchdog_send.send(f"Silence > {SILENCE_TIMEOUT}s")
                                    break
                                continue

                            if not data:
                                await watchdog_send.send("Server closed stream")
                                break

                            message = data.decode('utf-8').strip()
                            if message:
                                last_msg_time = time.time()
                                ts = time.strftime("%H:%M")
                                await messages_send.send(f"[{ts}] {message}")
                                await watchdog_send.send("New message in chat")

                    except anyio.get_cancelled_exc_class():
                        break
                    except (anyio.ClosedResourceError, anyio.BrokenResourceError) as e:
                        await watchdog_send.send(f"Stream error: {e}")
                        break

        except (ConnectionRefusedError, OSError, anyio.ClosedResourceError) as e:
            await watchdog_send.send(f"Сетевая ошибка: {e}")
            await status_send.send(gui.ReadConnectionStateChanged.CLOSED)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await watchdog_send.send(f"Неожиданная ошибка: {e}")
            await status_send.send(gui.ReadConnectionStateChanged.CLOSED)

        await anyio.sleep(2)
