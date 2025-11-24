from telethon import TelegramClient, events, Button
import json
import os
import sqlite3
from datetime import datetime

# ВСТАВЬ СВОИ ДАННЫЕ ЗДЕСЬ
api_id = 29385016                    # Твой API ID
api_hash = '3c57df8805ab5de5a23a032ed39b9af9'          # Твой API Hash
bot_token = '8334964804:AAHdieIWn4McjFWkSeoLq6UthsUodP1N5lY'    # Токен бота от BotFather

# ID администратора (замени на свой)
ADMIN_ID = 8000395560

client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registration_date TEXT,
            last_activity TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id):
    return user_id == ADMIN_ID

def save_user_to_db(user_id, username, first_name, last_name):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, username, first_name, last_name, registration_date, last_activity) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, now, now))
    
    conn.commit()
    conn.close()

def update_user_activity(user_id):
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute('''
        UPDATE users SET last_activity = ? WHERE user_id = ?
    ''', (now, user_id))
    
    conn.commit()
    conn.close()

def get_user_stats():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE date(last_activity) = date("now")')
    active_today = cursor.fetchone()[0]
    
    conn.close()
    return total_users, active_today

@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user_id = event.sender_id
    user = await event.get_sender()
    
    # Сохраняем пользователя в базу
    save_user_to_db(user_id, user.username, user.first_name, user.last_name)
    
    keyboard = [
        [Button.inline("Мой айди", b'my_id')],
        [Button.inline("Айди другого", b'other_id')]
    ]
    
    # Добавляем админские кнопки только для админа
    if is_admin(user_id):
        keyboard.extend([
            [Button.inline("📊 Статистика", b'stats'), Button.inline("📢 Рассылка", b'broadcast')],
            [Button.inline("💾 Скачать базу", b'download_db'), Button.inline("📤 Загрузить базу", b'upload_db')]
        ])
    
    await event.reply('Выберите опцию:', buttons=keyboard)

@client.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    update_user_activity(user_id)
    
    if event.data == b'my_id':
        await event.edit(f"🆔 Ваш ID: {user_id}")
    
    elif event.data == b'other_id':
        await event.edit("📩 Перешлите сообщение от нужного пользователя или напишите его юзернейм")
    
    elif event.data == b'stats':
        if not is_admin(user_id):
            await event.edit("❌ Доступ запрещен")
            return
        total_users, active_today = get_user_stats()
        await event.edit(f"📊 Статистика бота:\n\n👥 Всего пользователей: {total_users}\n🟢 Активных сегодня: {active_today}")
    
    elif event.data == b'broadcast':
        if not is_admin(user_id):
            await event.edit("❌ Доступ запрещен")
            return
        await event.edit("📢 Введите сообщение для рассылки:")
    
    elif event.data == b'download_db':
        if not is_admin(user_id):
            await event.edit("❌ Доступ запрещен")
            return
        try:
            await event.client.send_file(
                event.chat_id,
                'bot_database.db',
                caption='💾 База данных бота'
            )
            await event.delete()
        except Exception as e:
            await event.edit(f"❌ Ошибка при отправке базы: {str(e)}")
    
    elif event.data == b'upload_db':
        if not is_admin(user_id):
            await event.edit("❌ Доступ запрещен")
            return
        await event.edit("📤 Отправьте файл базы данных (bot_database.db) для загрузки")

@client.on(events.NewMessage)
async def message_handler(event):
    user_id = event.sender_id
    update_user_activity(user_id)
    
    # Обработка загрузки базы данных
    if is_admin(user_id) and event.message.file:
        try:
            file = await event.download_media(file='temp_db.db')
            os.rename('temp_db.db', 'bot_database.db')
            await event.reply("✅ База данных успешно обновлена!")
            return
        except Exception as e:
            await event.reply(f"❌ Ошибка при загрузке базы: {str(e)}")
            return
    
    # Обработка рассылки для админа
    if is_admin(user_id) and event.message.text and not event.message.text.startswith('/'):
        # Проверяем, не было ли это ответом на запрос рассылки
        if event.is_reply:
            replied_msg = await event.get_reply_message()
            if 'рассылк' in replied_msg.text.lower():
                message_text = event.message.text
                sent_count = 0
                
                await event.reply("🔄 Начинаю рассылку...")
                
                # Получаем всех пользователей из базы
                conn = sqlite3.connect('bot_database.db')
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM users')
                users = cursor.fetchall()
                conn.close()
                
                # Рассылаем сообщение всем пользователям
                for user_row in users:
                    try:
                        await client.send_message(user_row[0], f"📢 Рассылка:\n\n{message_text}")
                        sent_count += 1
                    except:
                        continue
                
                await event.reply(f"✅ Рассылка завершена\n\nОтправлено сообщений: {sent_count}")
                return
    
    # Игнорируем команды
    if event.message.text and event.message.text.startswith('/'):
        return
    
    # Обработка пересланных сообщений
    if event.message.forward:
        try:
            forward_header = event.message.forward
            sender_id = forward_header.sender_id
            
            if sender_id:
                try:
                    user = await client.get_entity(sender_id)
                    await event.reply(f"🆔 ID пользователя {user.first_name}: {user.id}")
                except:
                    await event.reply(f"🆔 ID пользователя: {sender_id}")
            else:
                await event.reply("❌ Не удалось получить ID отправителя")
        except Exception as e:
            await event.reply(f"❌ Ошибка при обработке пересланного сообщения: {str(e)}")
        return
    
    # Обработка юзернеймов (с @ и без)
    if event.message.text:
        text = event.message.text.strip()
        if text.startswith('@'):
            text = text[1:]
        
        if text:
            try:
                user = await client.get_entity(text)
                await event.reply(f"🆔 ID пользователя {user.first_name}: {user.id}")
            except Exception as e:
                await event.reply("❌ Пользователь не найден")

print("Бот запущен...")
client.run_until_disconnected()
