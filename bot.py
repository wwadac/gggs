import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, BusinessMessagesDeleted
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8316728730:AAEMrNJN8O7Efbk7TIDPphqGy5-4VrnigN8"
ADMIN_ID = 8593061718  # Твой Telegram ID
DATABASE = "messages.db"
# ===============================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ========== БАЗА ДАННЫХ ==========
async def init_db():
    """Создание таблиц в БД"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER,
                business_connection_id TEXT,
                chat_id INTEGER,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                text TEXT,
                caption TEXT,
                file_id TEXT,
                file_type TEXT,
                is_one_time INTEGER DEFAULT 0,
                date TEXT,
                PRIMARY KEY (message_id, chat_id)
            )
        ''')
        await db.commit()


async def save_message(msg: Message, business_connection_id: str = None):
    """Сохранение сообщения в БД"""
    
    file_id = None
    file_type = None
    is_one_time = False
    
    # Проверяем одноразовые сообщения
    if msg.photo:
        file_id = msg.photo[-1].file_id
        file_type = "photo"
        # Проверяем флаг одноразового сообщения
        if hasattr(msg, 'has_media_spoiler') and msg.has_media_spoiler:
            is_one_time = True
    elif msg.video:
        file_id = msg.video.file_id
        file_type = "video"
        if hasattr(msg, 'has_media_spoiler') and msg.has_media_spoiler:
            is_one_time = True
    elif msg.document:
        file_id = msg.document.file_id
        file_type = "document"
    elif msg.voice:
        file_id = msg.voice.file_id
        file_type = "voice"
    elif msg.video_note:
        file_id = msg.video_note.file_id
        file_type = "video_note"
    elif msg.sticker:
        file_id = msg.sticker.file_id
        file_type = "sticker"
    elif msg.audio:
        file_id = msg.audio.file_id
        file_type = "audio"
    elif msg.animation:
        file_id = msg.animation.file_id
        file_type = "animation"
    
    # Проверяем show_caption_above_media для одноразовых (новый API)
    # А также проверяем секретность через эффекты
    
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            INSERT OR REPLACE INTO messages 
            (message_id, business_connection_id, chat_id, user_id, username, 
             first_name, text, caption, file_id, file_type, is_one_time, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            msg.message_id,
            business_connection_id,
            msg.chat.id,
            msg.from_user.id if msg.from_user else None,
            msg.from_user.username if msg.from_user else None,
            msg.from_user.first_name if msg.from_user else None,
            msg.text,
            msg.caption,
            file_id,
            file_type,
            1 if is_one_time else 0,
            msg.date.isoformat()
        ))
        await db.commit()
    
    return file_id, file_type, is_one_time


async def get_message_by_id(chat_id: int, message_id: int):
    """Получение сообщения из БД по ID"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT * FROM messages 
            WHERE chat_id = ? AND message_id = ?
        ''', (chat_id, message_id))
        return await cursor.fetchone()


async def get_messages(chat_id: int, message_ids: list):
    """Получение сообщений из БД"""
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ','.join('?' * len(message_ids))
        cursor = await db.execute(f'''
            SELECT * FROM messages 
            WHERE chat_id = ? AND message_id IN ({placeholders})
        ''', [chat_id] + message_ids)
        return await cursor.fetchall()


# ========== ОБРАБОТЧИКИ ==========

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Я бот для сохранения удалённых и <b>одноразовых</b> сообщений.\n\n"
        "📌 <b>Как подключить:</b>\n"
        "1. Перейди в <b>Настройки → Telegram Business</b>\n"
        "2. Выбери <b>Чат-боты</b>\n"
        "3. Добавь этого бота\n\n"
        "🔥 <b>Фишка:</b> Чтобы сохранить одноразовое фото/видео,\n"
        "просто <b>ответь на него любым сообщением</b>!\n\n"
        "Бот пришлёт тебе сохранённую копию в ЛС 📩",
        parse_mode=ParseMode.HTML
    )


@dp.business_message()
async def handle_business_message(message: Message):
    """Обработка бизнес-сообщений"""
    
    # Сохраняем сообщение
    file_id, file_type, is_one_time = await save_message(message, message.business_connection_id)
    
    # Если это одноразовое сообщение - сразу отправляем в ЛС!
    if is_one_time and file_id:
        await send_saved_media_to_admin(message, file_id, file_type, is_one_time=True)
        print(f"🔥 Сохранено ОДНОРАЗОВОЕ сообщение от @{message.from_user.username}")
        return
    
    # Проверяем, является ли это ответом на сообщение
    if message.reply_to_message:
        reply_msg_id = message.reply_to_message.message_id
        
        # Получаем оригинальное сообщение из базы
        original = await get_message_by_id(message.chat.id, reply_msg_id)
        
        if original and original['file_id']:
            # Отправляем сохранённый файл админу
            await send_saved_media_to_admin_from_db(original, message.from_user)
            print(f"📩 Отправлено сохранённое медиа админу по запросу (ответ на сообщение)")
    
    print(f"💾 Сохранено сообщение от @{message.from_user.username}: {message.text or '[медиа]'}")


async def send_saved_media_to_admin(message: Message, file_id: str, file_type: str, is_one_time: bool = False):
    """Отправка медиа админу"""
    
    prefix = "🔥 <b>ОДНОРАЗОВОЕ СООБЩЕНИЕ!</b>\n\n" if is_one_time else "📩 <b>Сохранённое сообщение:</b>\n\n"
    
    caption = (
        f"{prefix}"
        f"👤 <b>От:</b> {message.from_user.first_name} (@{message.from_user.username})\n"
        f"🆔 <b>Chat ID:</b> <code>{message.chat.id}</code>\n"
        f"📅 <b>Дата:</b> {message.date.strftime('%d.%m.%Y %H:%M')}"
    )
    
    try:
        if file_type == 'photo':
            await bot.send_photo(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'video':
            await bot.send_video(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'animation':
            await bot.send_animation(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'document':
            await bot.send_document(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'voice':
            await bot.send_voice(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'video_note':
            await bot.send_message(ADMIN_ID, caption, parse_mode=ParseMode.HTML)
            await bot.send_video_note(ADMIN_ID, file_id)
        elif file_type == 'audio':
            await bot.send_audio(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'sticker':
            await bot.send_message(ADMIN_ID, caption, parse_mode=ParseMode.HTML)
            await bot.send_sticker(ADMIN_ID, file_id)
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"⚠️ Ошибка отправки: {e}")


async def send_saved_media_to_admin_from_db(msg_data, from_user):
    """Отправка медиа из БД админу"""
    
    is_one_time = msg_data['is_one_time'] == 1
    prefix = "🔥 <b>ОДНОРАЗОВОЕ СООБЩЕНИЕ!</b>\n\n" if is_one_time else "📩 <b>Сохранённое сообщение:</b>\n\n"
    
    caption = (
        f"{prefix}"
        f"👤 <b>От:</b> {msg_data['first_name']} (@{msg_data['username']})\n"
        f"🆔 <b>Chat ID:</b> <code>{msg_data['chat_id']}</code>\n"
        f"📅 <b>Дата:</b> {msg_data['date']}"
    )
    
    if msg_data['caption']:
        caption += f"\n📝 <b>Подпись:</b> {msg_data['caption']}"
    
    file_id = msg_data['file_id']
    file_type = msg_data['file_type']
    
    try:
        if file_type == 'photo':
            await bot.send_photo(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'video':
            await bot.send_video(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'animation':
            await bot.send_animation(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'document':
            await bot.send_document(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'voice':
            await bot.send_voice(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'video_note':
            await bot.send_message(ADMIN_ID, caption, parse_mode=ParseMode.HTML)
            await bot.send_video_note(ADMIN_ID, file_id)
        elif file_type == 'audio':
            await bot.send_audio(ADMIN_ID, file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif file_type == 'sticker':
            await bot.send_message(ADMIN_ID, caption, parse_mode=ParseMode.HTML)
            await bot.send_sticker(ADMIN_ID, file_id)
        
        print(f"✅ Медиа отправлено админу")
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"⚠️ Ошибка: {e}")


@dp.edited_business_message()
async def handle_edited_business_message(message: Message):
    """Обработка отредактированных сообщений"""
    
    old_messages = await get_messages(message.chat.id, [message.message_id])
    
    if old_messages:
        old = old_messages[0]
        await bot.send_message(
            ADMIN_ID,
            f"✏️ <b>Сообщение отредактировано!</b>\n\n"
            f"👤 Клиент: {message.from_user.first_name} (@{message.from_user.username})\n\n"
            f"📝 <b>Было:</b>\n{old['text'] or old['caption'] or '[медиа]'}\n\n"
            f"📝 <b>Стало:</b>\n{message.text or message.caption or '[медиа]'}",
            parse_mode=ParseMode.HTML
        )
    
    await save_message(message, message.business_connection_id)


@dp.deleted_business_messages()
async def handle_deleted_messages(event: BusinessMessagesDeleted):
    """Обработка удалённых сообщений"""
    
    deleted = await get_messages(event.chat.id, event.message_ids)
    
    if not deleted:
        await bot.send_message(
            ADMIN_ID,
            f"🗑 <b>Удалено {len(event.message_ids)} сообщений</b>\n"
            f"👤 Чат: {event.chat.first_name} (ID: {event.chat.id})\n\n"
            f"⚠️ Сообщения не найдены в базе",
            parse_mode=ParseMode.HTML
        )
        return
    
    for msg in deleted:
        text = msg['text'] or msg['caption'] or ''
        is_one_time = msg['is_one_time'] == 1
        
        type_label = "🔥 ОДНОРАЗОВОЕ" if is_one_time else "🗑 УДАЛЁННОЕ"
        
        notification = (
            f"{type_label} <b>СООБЩЕНИЕ!</b>\n\n"
            f"👤 <b>От:</b> {msg['first_name']} (@{msg['username']})\n"
            f"🆔 <b>Chat ID:</b> <code>{msg['chat_id']}</code>\n"
            f"📅 <b>Дата:</b> {msg['date']}\n\n"
        )
        
        if msg['file_type'] and msg['file_id']:
            notification += f"📎 <b>Тип:</b> {msg['file_type']}\n"
            if text:
                notification += f"📝 <b>Подпись:</b> {text}\n"
            
            await bot.send_message(ADMIN_ID, notification, parse_mode=ParseMode.HTML)
            
            try:
                if msg['file_type'] == 'photo':
                    await bot.send_photo(ADMIN_ID, msg['file_id'])
                elif msg['file_type'] == 'video':
                    await bot.send_video(ADMIN_ID, msg['file_id'])
                elif msg['file_type'] == 'document':
                    await bot.send_document(ADMIN_ID, msg['file_id'])
                elif msg['file_type'] == 'voice':
                    await bot.send_voice(ADMIN_ID, msg['file_id'])
                elif msg['file_type'] == 'video_note':
                    await bot.send_video_note(ADMIN_ID, msg['file_id'])
                elif msg['file_type'] == 'sticker':
                    await bot.send_sticker(ADMIN_ID, msg['file_id'])
                elif msg['file_type'] == 'audio':
                    await bot.send_audio(ADMIN_ID, msg['file_id'])
                elif msg['file_type'] == 'animation':
                    await bot.send_animation(ADMIN_ID, msg['file_id'])
            except Exception as e:
                await bot.send_message(ADMIN_ID, f"⚠️ Не удалось отправить файл: {e}")
        else:
            notification += f"💬 <b>Текст:</b>\n<code>{text}</code>"
            await bot.send_message(ADMIN_ID, notification, parse_mode=ParseMode.HTML)


@dp.business_connection()
async def handle_business_connection(connection: types.BusinessConnection):
    """Подключение/отключение бота"""
    
    if connection.is_enabled:
        await bot.send_message(
            connection.user.id,
            "✅ <b>Бот подключён!</b>\n\n"
            "🔥 Чтобы сохранить одноразовое фото/видео:\n"
            "Просто <b>ответь на него</b> любым сообщением!\n\n"
            "Бот автоматически пришлёт тебе копию 📩",
            parse_mode=ParseMode.HTML
        )
    else:
        await bot.send_message(
            connection.user.id,
            "❌ <b>Бот отключён.</b>",
            parse_mode=ParseMode.HTML
        )


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика"""
    if message.from_user.id != ADMIN_ID:
        return
    
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        count = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE is_one_time = 1")
        one_time_count = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(DISTINCT chat_id) FROM messages")
        chats = (await cursor.fetchone())[0]
    
    await message.answer(
        f"📊 <b>Статистика:</b>\n\n"
        f"💬 Всего сообщений: <b>{count}</b>\n"
        f"🔥 Одноразовых: <b>{one_time_count}</b>\n"
        f"👥 Уникальных чатов: <b>{chats}</b>",
        parse_mode=ParseMode.HTML
    )


# ========== ЗАПУСК ==========
async def main():
    await init_db()
    print("🚀 Бот запущен!")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("🔥 Режим сохранения одноразовых сообщений активен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
