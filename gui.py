import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter.messagebox import showerror
import anyio
from enum import Enum


class TkAppClosed(Exception):
    pass


class InvalidToken(Exception):
    def show_error_dialog(self):
        error_root = tk.Tk()
        error_root.withdraw()
        showerror("Ошибка токена", str(self))
        error_root.destroy()


class ReadConnectionStateChanged(Enum):
    INITIATED = 'устанавливаем соединение'
    ESTABLISHED = 'соединение установлено'
    CLOSED = 'соединение закрыто'

    def __str__(self):
        return str(self.value)


class SendingConnectionStateChanged(Enum):
    INITIATED = 'устанавливаем соединение'
    ESTABLISHED = 'соединение установлено'
    CLOSED = 'соединение закрыто'

    def __str__(self):
        return str(self.value)


class NicknameReceived:
    def __init__(self, nickname):
        self.nickname = nickname


async def update_tk(root, interval=1/120):
    while True:
        try:
            root.update()
        except tk.TclError:
            raise TkAppClosed()
        await anyio.sleep(interval)


async def update_conversation_history(panel, msg_recv):
    async with msg_recv:
        async for msg in msg_recv:
            panel.config(state='normal')
            if panel.index('end-1c') != '1.0':
                panel.insert('end', '\n')
            panel.insert('end', msg)
            panel.yview('end')
            panel.config(state='disabled')


async def update_status_panel(nick_label, read_label, write_label, status_recv):
    read_label['text'] = 'Чтение: нет соединения'
    write_label['text'] = 'Отправка: нет соединения'
    nick_label['text'] = 'Имя пользователя: неизвестно'
    
    async with status_recv:
        async for msg in status_recv:
            if isinstance(msg, ReadConnectionStateChanged):
                read_label['text'] = f'Чтение: {msg.value}'
            elif isinstance(msg, SendingConnectionStateChanged):
                write_label['text'] = f'Отправка: {msg.value}'
            elif isinstance(msg, NicknameReceived):
                nick_label['text'] = f'Имя пользователя: {msg.nickname}'


async def draw(root, msg_recv, status_recv, send_channel):
    root.title('Чат Майнкрафтера')
    root.geometry('800x600')

    status_frame = tk.Frame(root)
    status_frame.pack(side='bottom', fill='x')
    
    nick_label = tk.Label(status_frame, fg='grey', font='arial 10', anchor='w')
    nick_label.pack(side='top', fill='x')
    read_label = tk.Label(status_frame, fg='grey', font='arial 10', anchor='w')
    read_label.pack(side='top', fill='x')
    write_label = tk.Label(status_frame, fg='grey', font='arial 10', anchor='w')
    write_label.pack(side='top', fill='x')

    conversation_panel = ScrolledText(root, wrap='none')
    conversation_panel.pack(side='top', fill='both', expand=True)

    input_frame = tk.Frame(root)
    input_frame.pack(side='bottom', fill='x')
    
    input_field = tk.Entry(input_frame)
    input_field.pack(side='left', fill='x', expand=True)
    
    send_button = tk.Button(input_frame, text='Отправить')
    send_button.pack(side='left')

    def on_send():
        text = input_field.get().strip()
        if text:
            try:
                send_channel.send_nowait(text)
                input_field.delete(0, tk.END)
            except anyio.WouldBlock:
                print("Буфер отправки переполнен, сообщение пропущено")
            except Exception:
                pass  

    send_button.config(command=on_send)
    input_field.bind('<Return>', lambda e: on_send())

    async with anyio.create_task_group() as tg:
        tg.start_soon(update_tk, root)
        tg.start_soon(update_conversation_history, conversation_panel, msg_recv)
        tg.start_soon(update_status_panel, nick_label, read_label, write_label, status_recv)
