import tkinter as tk
from tkinter import messagebox
import anyio
import json
import threading
import queue

SERVER_HOST = 'minechat.dvmn.org'
SERVER_PORT = 5050
CREDENTIALS_FILE = 'token_file.txt'


async def connect_to_server(host: str, port: int, timeout: float = 10.0):
    reader, writer = await anyio.connect_tcp(host, port)
    return reader, writer


async def send_registration_request(reader, writer, nickname: str, timeout: float = 10.0):
    async with anyio.fail_after(timeout):
        await reader.receive_until(b'\n', 1024)
    writer.write(b'\n')
    await writer.drain()
    
    async with anyio.fail_after(timeout):
        await reader.receive_until(b'\n', 1024)
    writer.write(f"{nickname}\n".encode('utf-8'))
    await writer.drain()


async def receive_server_response(reader, timeout: float = 10.0):
    async with anyio.fail_after(timeout):
        raw_response = await reader.receive_until(b'\n', 1024)
    response_data = json.loads(raw_response.decode('utf-8'))
    
    token = response_data.get('account_hash')
    server_nick = response_data.get('nickname')
    return token, server_nick


def save_credentials(file_path: str, token: str, nickname: str):
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(f"{token}\n{nickname}\n")


async def register_on_server(nickname: str, result_q: queue.Queue):
    writer = None
    try:
        reader, writer = await connect_to_server(SERVER_HOST, SERVER_PORT)
        await send_registration_request(reader, writer, nickname)
        token, server_nick = await receive_server_response(reader)
        
        if not token:
            result_q.put(('error', 'Сервер не вернул токен. Попробуйте другой ник.'))
            return
        
        final_nick = server_nick if server_nick else nickname
        save_credentials(CREDENTIALS_FILE, token, final_nick)
        
        result_q.put(('success', f"Регистрация успешна!\nВаш никнейм: {final_nick}\nДанные сохранены в {CREDENTIALS_FILE}"))
        
    except anyio.TimeoutError:
        result_q.put(('error', 'Таймаут соединения. Проверьте интернет.'))
    except json.JSONDecodeError:
        result_q.put(('error', 'Некорректный ответ сервера. Попробуйте позже.'))
    except Exception as e:
        result_q.put(('error', f'Ошибка: {str(e)}'))
    finally:
        if writer:
            try:
                await writer.aclose()
            except Exception:
                pass


def create_gui():
    root = tk.Tk()
    root.title("Регистрация в чате")
    root.geometry("350x200")
    root.resizable(False, False)

    tk.Label(root, text="Введите желаемый никнейм:", font=('Arial', 10)).pack(pady=(20, 5))
    
    nickname_entry = tk.Entry(root, width=30, font=('Arial', 10))
    nickname_entry.pack(pady=5)
    nickname_entry.focus()

    status_label = tk.Label(root, text="", font=('Arial', 9), fg='grey')
    status_label.pack(pady=5)

    register_btn = tk.Button(root, text="Зарегистрироваться", font=('Arial', 10), bg='#4CAF50', fg='white')
    register_btn.pack(pady=10)
    
    return root, nickname_entry, status_label, register_btn


def start_registration(nickname_entry, status_label, register_btn, root):
    nickname = nickname_entry.get().strip()
    if not nickname:
        messagebox.showwarning("Внимание", "Никнейм не может быть пустым.")
        return

    nickname_entry.config(state=tk.DISABLED)
    register_btn.config(state=tk.DISABLED, bg='#ccc')
    status_label.config(text="Подключение к серверу...", fg='blue')
    root.update_idletasks()
    
    result_queue = queue.Queue()

    def run_async_register():
        anyio.run(register_on_server, nickname, result_queue)

    thread = threading.Thread(target=run_async_register, daemon=True)
    thread.start()

    def check_result():
        try:
            status, message = result_queue.get_nowait()
            status_label.config(text=message, fg='green' if status == 'success' else 'red')
            
            if status == 'success':
                messagebox.showinfo("Успех", message)
                root.destroy()
            else:
                messagebox.showerror("Ошибка", message)
                nickname_entry.config(state=tk.NORMAL)
                register_btn.config(state=tk.NORMAL, bg='#4CAF50')
        except queue.Empty:
            root.after(100, check_result)

    check_result()


def main():
    root, nickname_entry, status_label, register_btn = create_gui()
    
    register_btn.config(command=lambda: start_registration(nickname_entry, status_label, register_btn, root))
    nickname_entry.bind('<Return>', lambda e: start_registration(nickname_entry, status_label, register_btn, root))
    
    root.mainloop()


if __name__ == '__main__':
    main()
