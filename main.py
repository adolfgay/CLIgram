from telethon import TelegramClient, events
from telethon.tl.types import Channel
import asyncio
import os
from dotenv import load_dotenv
from asciiGenerator import *
from audioplayer import AudioPlayer
import pyaudio
import wave
from pydub import AudioSegment
# TODO: Расшифровка гс через vosk

# ---Инициализация---
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
client = TelegramClient('bot', API_ID , API_HASH)
input_task = None
CHUNK = 1024
FORMAT = pyaudio.paInt16 
CHANNELS = 1              # Моно
RATE = 44100
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


#--- Просмотр профиля пользовтеля ---
async def view_profile(profile_id):
    profile = await client.get_entity(profile_id)

    profile_picture = await client.download_profile_photo(profile)
    await client.loop.run_in_executor(None, generate, profile_picture)
    os.remove(profile_picture) # удаляем временный файл
    os.remove("ascii_art.txt")

    print(f"ID: {profile.id}")
    print(f"Номер телефона: +{profile.phone if profile.phone != None else "скрыт"}")
    print(f"Имя пользователя: {profile.username}")
    print(f"Имя: {profile.first_name} {profile.last_name if profile.last_name != None else " "}")
    print(f"Telegram Premium: {"Да" if profile.premium else "Нет"}")
    print(f"Спамблок: {"Да" if profile.restricted else "Нет"}")
    print("\n--- Возврат в режим ожидания ввода номера чата/сообщения ---")

    input_task = client.loop.create_task(get_target_user())
    return


async def get_target_user():
#---Основное окно с ожиданием/выбором чата---
    global input_task
    try:
        target = await client.loop.run_in_executor(None, input, "Кому написать(номер)? (или ждем сообщения)(0 для выхода, 01 для просмотра своего профиля): ")
        # Вызов функций
        if target == '0':
            try:
                client.disconnect()
                for f in os.listdir(os.getcwd()):
                    if f.startswith('voice'):
                        os.remove(f)
            except Exception as e:
                print(f"[ОШИБКА ОТКЛЮЧЕНИЯ/УДАЛЕНИЯ] {e}")
                
        elif target == '01':
            await view_profile(await client.get_me())
            input_task = client.loop.create_task(get_target_user())
            return
        # Получаем id и имя чата
        target_int = int(target)
        target_tuple = chats.get(target_int)
        if target_tuple:
            target_id, target_name = target_tuple
            await read_chat_history(target_id, is_new_chat=True) # Переходим в редим просмотра чата
            input_task = client.loop.create_task(process_history_command(target_name, target_id))
            return 
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
        print(f"\n[ИГНОР] Получен новый пост от канала {sender.title}: {event.text}") # не отвечаем на каналы
        input_task = client.loop.create_task(get_target_user())
        return 
    input_task = client.loop.create_task(get_target_user())


# ---Выводит историю сообщений для указанного chat_id, используя offset_id для пролистывания---
async def read_chat_history(chat_id, limit=10, is_new_chat=False):
    voice_msgs = {}
    voice_msgs_counter = 0
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
            if isinstance(sender, Channel):
                # Если канал
                sender_name = sender.title
            else:
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

            elif msg.voice:
                # Если есть голосовое сообщение предлагаем их послушать
                path = await msg.download_media()
                voice_msgs_counter += 1
                voice_msgs.update({voice_msgs_counter:path})

            print(f"[{msg.date.strftime('%H:%M')}] {sender_name}: {msg.text}")

        print("------------------------------------------------------------------")

        if voice_msgs_counter != 0:
            try:
                print(f"Голосовые сообщения {voice_msgs}")
                command = await client.loop.run_in_executor(None, input, "\nКакое прослушать? (0 - не слушать, 01 - все ): ")
                answer = int(command)
                if answer == 0:
                    pass

                elif command == '01':
                    for audio in voice_msgs.values():
                        await client.loop.run_in_executor(None, play_audio, audio)
                else:
                    await client.loop.run_in_executor(None, play_audio, voice_msgs.get(answer))
            except Exception as e:
                print(f"[ОШИБКА ВОСПРОИЗВЕДЕНИЯ]: {e}")

        history_state['offset_id'] = oldest_id 
        
    except Exception as e:
        print(f"[ОШИБКА ИСТОРИИ] Не удалось загрузить историю: {e}")
        history_state['in_history_mode'] = False


def play_audio(file_path):
    """Синхронно воспроизводит аудио и затем удаляет файл."""
    try:
        player = AudioPlayer(file_path)
        player.play(block=True)
        
    except Exception as e:
        print(f"[ОШИБКА ВОСПРОИЗВЕДЕНИЯ] Не удалось воспроизвести {file_path}: {e}")
    finally:
        # Удаление файла после завершения проигрывания
        if os.path.exists(file_path):
            os.remove(file_path)
        

#---Асинхронно ждет команду пользователя, пока активен режим просмотра чата.---
async def process_history_command(target_name, target_id):
    global input_task
    
    command = await client.loop.run_in_executor(None, input, "\nВведите команду: ('еще' / 'назад' / 'написать' / 'отправить гс' / 'отправить файл' / 'профиль'): ")
    
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

    elif command == 'написать':
        # Отпралвяет сообщение в выбранном чате
        message = await client.loop.run_in_executor(None, input, f"Сообщение для {target_name}: ")
        await client.send_message(target_id, message)
        print(f"\n[УСПЕХ] Сообщение отправлено.")
        history_state['in_history_mode'] = False
        history_state['chat_id'] = None
        history_state['offset_id'] = 0
        print("\n--- Возврат в режим ожидания ввода номера чата/сообщения ---")
        input_task = client.loop.create_task(get_target_user())

    elif command == 'отправить гс':
        try:
            duration = await client.loop.run_in_executor(None, input, "Введите длину ГС: ")
            voice_msg_path = await client.loop.run_in_executor(None, record_audio, int(duration))
            await client.send_file(target_id, voice_msg_path, voice_note=True)
            print(f"\n[УСПЕХ] Сообщение отправлено.")
            if os.path.exists(voice_msg_path):
                os.remove(voice_msg_path)
            history_state['in_history_mode'] = False
            history_state['chat_id'] = None
            history_state['offset_id'] = 0
            print("\n--- Возврат в режим ожидания ввода номера чата/сообщения ---")
            input_task = client.loop.create_task(get_target_user())
        except Exception as e:
            print(f"[ОШИБКА ОТПРАВКИ ГС] {e}")

    elif command == 'отправить файл':
        try:
            file_path = await client.loop.run_in_executor(None, input, "Введите путь до файла:")
            await client.send_file(target_id, file_path)
            print(f"\n[УСПЕХ] Файл отправлен.")
            history_state['in_history_mode'] = False
            history_state['chat_id'] = None
            history_state['offset_id'] = 0
            print("\n--- Возврат в режим ожидания ввода номера чата/сообщения ---")
            input_task = client.loop.create_task(get_target_user())
        except Exception as e:
            print(f"[ОШИБКА ОТПРАВКИ ФАЙЛА] {e}")

    elif command == 'профиль':
        await view_profile(target_id)
        history_state['in_history_mode'] = False
        history_state['chat_id'] = None
        history_state['offset_id'] = 0
       
    else:
        print("Неизвестная команда. Введите 'еще', 'назад','написать', 'отправить гс' или 'профиль'")
        input_task = client.loop.create_task(process_history_command(target_name, target_id)) # Повторяем ожидание команды
 

def record_audio(duration_seconds):
    try:
        # 1. Инициализация
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        output_filename = 'voicemsg.wav'

        print("\n[ЗАПИСЬ] Говорите! (Продолжительность: {} сек)".format(duration_seconds))
        frames = []

        # 2. Запись данных
        for i in range(0, int(RATE / CHUNK * duration_seconds)):
            data = stream.read(CHUNK)
            frames.append(data)

        print("[ЗАПИСЬ] Запись завершена.")

        # 3. Остановка и очистка
        stream.stop_stream()
        stream.close()
        p.terminate()

        # 4. Сохранение в WAV
        wf = wave.open(output_filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
    except Exception as e:
        print(f"[ОШИБКА ЗАПИСИ] {e}")
    # 5. КОНВЕРТАЦИЯ В .OGA 
    # (FFmpeg необходимо установить отдельно в ОС)
    try:
        ogg_filename = output_filename.replace('.wav', '.oga')
        audio = AudioSegment.from_wav(output_filename)
        audio.export(ogg_filename, format="ogg")
        os.remove(output_filename) # Удаляем временный WAV
        print(f"[КОНВЕРТАЦИЯ] Файл готов: {ogg_filename}")
        return ogg_filename
    except Exception as e:
        print(f"[ОШИБКА КОНВЕРТАЦИИ] {e}. ")
        return output_filename


# --- Запуск клиента ---
if __name__ == "__main__":
    try:
        client.start()
        client.loop.run_until_complete(main())
        input_task = client.loop.create_task(get_target_user())
        client.run_until_disconnected()
    except Exception as e:
        print(f"\n[КРИТИЧЕСКАЯ ОШИБКА ЗАПУСКА] Убедитесь, что API_ID/API_HASH правильные и сессия создана: {e}")