from telethon import TelegramClient, events
import asyncio
import os
from dotenv import load_dotenv
from asciiGenerator import *

# ---Инициализация---
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
client = TelegramClient('bot', API_ID , API_HASH)
input_task = None
history_state = {
    'chat_id': None,        
    'offset_id': 0,         
    'in_history_mode': False 
}

# ---Основная функция с выводом чатов---
async def main():  
    print("Ваши чаты")
    num = 1
    # Список чатов
    global chats
    chats = {}
    async for dialog in client.iter_dialogs():
        print(f"{num}. {dialog.name}")
        chats.update({num:(dialog.id, dialog.name)}) # Номер для выбора, id и имя чата
        num+=1


async def get_target_user():
#---Основное окно с ожиданием/выбором чата---
    global input_task
    try:
        target = await client.loop.run_in_executor(None, input, "Кому написать? (или ждем сообщения)(0 для выхода): ")
        # Получаем id и имя чата
        target_int = int(target)
        target_tuple = chats.get(target_int)
        if target_tuple:
            target_id, target_name = target_tuple
            await read_chat_history(target_id, is_new_chat=True) # Переходим в редим просмотра чата
            input_task = client.loop.create_task(process_history_command(target_name, target_id))
            return 
        elif target_int == 0:
            client.disconnect()
        else:
            print('такого чата нет!')
    except ValueError:
        print("введите номер чата")
        input_task = client.loop.create_task(get_target_user())
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА] в get_target_user: {e}")
        input_task = client.loop.create_task(get_target_user())


#---Обработчик новых сообщений---
@client.on(events.NewMessage())
async def handler(event):
    global input_task
    if input_task and not input_task.done():
        input_task.cancel()
    sender = await event.get_sender()
    if not event.is_channel:
        print(f"\n\n--- ВХОДЯЩЕЕ СООБЩЕНИЕ ---")
        print(f"От: {sender.first_name}")
        print(f"Текст: {event.text}")
        print("--------------------------")
        answer = await client.loop.run_in_executor(None, input, "Ответить Y/N? Д/Н? ")
        if answer.lower() in ('y', 'д'):
            # Отвечаем на сообщение
            answer_to_target = await client.loop.run_in_executor(None, input, 'Ваш ответ: ')
            await event.reply(answer_to_target)
        else:
            pass
    else:
        print(f"\n[ИГНОР] Получен новый пост от канала ID: {event.chat_id}.") # не отвечаем на каналы
        input_task = client.loop.create_task(get_target_user())
        return 
    input_task = client.loop.create_task(get_target_user())


async def read_chat_history(chat_id, limit=10, is_new_chat=False):
    """
    Выводит историю сообщений для указанного chat_id, используя offset_id для пролистывания.
    """
    global history_state
    
    if is_new_chat:
        history_state['chat_id'] = chat_id
        history_state['offset_id'] = 0
        history_state['in_history_mode'] = True

    try:

        messages = await client.get_messages(
            history_state['chat_id'], 
            limit=limit, 
            offset_id=history_state['offset_id']
        )
        if not messages:
            print("\n--- Достигнут конец истории сообщений ---")
            history_state['offset_id'] = 0 
            return
        print(f"\n--- История чата ({len(messages)} сообщений, от старых к новым) ---")
        oldest_id = messages[-1].id 
        for msg in reversed(messages):
            sender = await msg.get_sender()
            sender_name = sender.first_name if sender.first_name else f"ID: {sender.id}"
            if msg.out:
                sender_name = "Вы"
            if msg.photo:
                # Если в чате есть фото выводим его в ASCII 
                try:
                    path = await msg.download_media()
                    await client.loop.run_in_executor(None, generate, path)
                    os.remove(path) # удаляем временный файл
                    os.remove("ascii_art.txt")
                except Exception as e:
                    print(f"[ОШИБКА ГЕНЕРАЦИИ ASCII] {e}")
            
            print(f"[{msg.date.strftime('%H:%M')}] {sender_name}: {msg.text}")

        print("------------------------------------------------------------------")

        history_state['offset_id'] = oldest_id 
        
    except Exception as e:
        print(f"[ОШИБКА ИСТОРИИ] Не удалось загрузить историю: {e}")
        history_state['in_history_mode'] = False


#---Асинхронно ждет команду пользователя, пока активен режим просмотра чата.---
async def process_history_command(target_name, target_id):
    global input_task
    
    command = await client.loop.run_in_executor(None, input, "\nВведите команду: ('еще' / 'назад' / 'написать'): ")
    
    command = command.lower()

    if command in ('еще', 'ещё'):
        # Если "еще", просто загружаем следующую порцию сообщений
        await read_chat_history(history_state['chat_id'], is_new_chat=False)
        input_task = client.loop.create_task(process_history_command(target_name, target_id)) # Ждем следующую команду
        
    elif command in ('назад', 'назад'):
        # Если "назад", выходим из режима просмотра чата и возвращаемся к основному вводу
        history_state['in_history_mode'] = False
        history_state['chat_id'] = None
        history_state['offset_id'] = 0
        print("\n--- Возврат в режим ожидания ввода номера чата/сообщения ---")
        input_task = client.loop.create_task(get_target_user()) # Запускаем основной ввод

    elif command == "написать":
        # Отпралвяет сообщение в выбранном чате
        message = await client.loop.run_in_executor(None, input, f"Сообщение для {target_name}: ")
        await client.send_message(target_id, message)
        print(f"\n[УСПЕХ] Сообщение отправлено.")
        history_state['in_history_mode'] = False
        history_state['chat_id'] = None
        history_state['offset_id'] = 0
        print("\n--- Возврат в режим ожидания ввода номера чата/сообщения ---")
        input_task = client.loop.create_task(get_target_user())
       
    else:
        print("Неизвестная команда. Введите 'еще', 'назад' или 'написать'")
        input_task = client.loop.create_task(process_history_command(target_name, target_id)) # Повторяем ожидание команды
 

# --- Запуск клиента ---
if __name__ == "__main__":
    try:
        client.start()
        client.loop.run_until_complete(main())
        input_task = client.loop.create_task(get_target_user())
        client.run_until_disconnected()
    except Exception as e:
        print(f"\n[КРИТИЧЕСКАЯ ОШИБКА ЗАПУСКА] Убедитесь, что API_ID/API_HASH правильные и сессия создана: {e}")