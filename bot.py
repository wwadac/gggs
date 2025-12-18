import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, BusinessMessagesDeleted
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8316728730:AAGeu3RWRAJo_SWe8-vBhWtoPGJX3iTx79Q"  # Получи у @BotFather
ADMIN_ID = 8593061718  # Твой Telegram ID (узнай у @userinfobot)
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
                date TEXT,
                PRIMARY KEY (message_id, chat_id)
            )
        ''')
        await db.commit()


async def save_message(msg: Message, business_connection_id: str = None):
    """Сохранение сообщения в БД"""
    
    # Определяем тип файла
    file_id = None
    file_type = None
    
    if msg.photo:
        file_id = msg.photo[-1].file_id
        file_type = "photo"
    elif msg.video:
        file_id = msg.video.file_id
        file_type = "video"
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
    
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            INSERT OR REPLACE INTO messages 
            (message_id, business_connection_id, chat_id, user_id, username, 
             first_name, text, caption, file_id, file_type, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            msg.date.isoformat()
        ))
        await db.commit()


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
        "Я бот для сохранения удалённых сообщений.\n\n"
        "📌 <b>Как подключить:</b>\n"
        "1. Перейди в <b>Настройки → Telegram Business</b>\n"
        "2. Выбери <b>Чат-боты</b>\n"
        "3. Добавь этого бота\n\n"
        "После подключения я буду сохранять все сообщения от клиентов "
        "и уведомлять тебя об удалённых! 🔔",
        parse_mode=ParseMode.HTML
    )


@dp.business_message()
async def handle_business_message(message: Message):
    """Обработка бизнес-сообщений (от клиентов)"""
    
    # Сохраняем сообщение
    await save_message(message, message.business_connection_id)
    
    print(f"💾 Сохранено сообщение от @{message.from_user.username}: {message.text or '[медиа]'}")


@dp.edited_business_message()
async def handle_edited_business_message(message: Message):
    """Обработка отредактированных сообщений"""
    
    # Получаем старую версию
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
    
    # Обновляем в базе
    await save_message(message, message.business_connection_id)


@dp.deleted_business_messages()
async def handle_deleted_messages(event: BusinessMessagesDeleted):
    """🔥 ГЛАВНАЯ ФИЧА: Обработка удалённых сообщений"""
    
    # Получаем удалённые сообщения из базы
    deleted = await get_messages(event.chat.id, event.message_ids)
    
    if not deleted:
        await bot.send_message(
            ADMIN_ID,
            f"🗑 <b>Удалено {len(event.message_ids)} сообщений</b>\n"
            f"👤 Чат: {event.chat.first_name} (ID: {event.chat.id})\n\n"
            f"⚠️ Сообщения не найдены в базе (возможно, бот был подключён позже)",
            parse_mode=ParseMode.HTML
        )
        return
    
    for msg in deleted:
        text = msg['text'] or msg['caption'] or ''
        
        # Формируем уведомление
        notification = (
            f"🗑 <b>УДАЛЁННОЕ СООБЩЕНИЕ!</b>\n\n"
            f"👤 <b>От:</b> {msg['first_name']} (@{msg['username']})\n"
            f"🆔 <b>Chat ID:</b> <code>{msg['chat_id']}</code>\n"
            f"📅 <b>Дата:</b> {msg['date']}\n\n"
        )
        
        # Отправляем контент
        if msg['file_type'] and msg['file_id']:
            notification += f"📎 <b>Тип:</b> {msg['file_type']}\n"
            if text:
                notification += f"📝 <b>Подпись:</b> {text}\n"
            
            await bot.send_message(ADMIN_ID, notification, parse_mode=ParseMode.HTML)
            
            # Отправляем медиафайл
            try:
                if msg['file_type'] == 'photo':
                    await bot.send_photo(ADMIN_ID, msg['file_id'], caption="👆 Удалённое фото")
                elif msg['file_type'] == 'video':
                    await bot.send_video(ADMIN_ID, msg['file_id'], caption="👆 Удалённое видео")
                elif msg['file_type'] == 'document':
                    await bot.send_document(ADMIN_ID, msg['file_id'], caption="👆 Удалённый документ")
                elif msg['file_type'] == 'voice':
                    await bot.send_voice(ADMIN_ID, msg['file_id'], caption="👆 Удалённое голосовое")
                elif msg['file_type'] == 'video_note':
                    await bot.send_video_note(ADMIN_ID, msg['file_id'])
                elif msg['file_type'] == 'sticker':
                    await bot.send_sticker(ADMIN_ID, msg['file_id'])
                elif msg['file_type'] == 'audio':
                    await bot.send_audio(ADMIN_ID, msg['file_id'], caption="👆 Удалённое аудио")
            except Exception as e:
                await bot.send_message(ADMIN_ID, f"⚠️ Не удалось отправить файл: {e}")
        else:
            notification += f"💬 <b>Текст:</b>\n<code>{text}</code>"
            await bot.send_message(ADMIN_ID, notification, parse_mode=ParseMode.HTML)
    
    print(f"🗑 Отправлено {len(deleted)} удалённых сообщений админу")


@dp.business_connection()
async def handle_business_connection(connection: types.BusinessConnection):
    """Обработка подключения/отключения бота к бизнес-аккаунту"""
    
    if connection.is_enabled:
        await bot.send_message(
            connection.user.id,
            "✅ <b>Бот успешно подключён!</b>\n\n"
            "Теперь я буду сохранять все сообщения от клиентов "
            "и уведомлять тебя об удалённых.",
            parse_mode=ParseMode.HTML
        )
        print(f"✅ Подключён к бизнес-аккаунту: @{connection.user.username}")
    else:
        await bot.send_message(
            connection.user.id,
            "❌ <b>Бот отключён от бизнес-аккаунта.</b>",
            parse_mode=ParseMode.HTML
        )


@dp.message(F.text == "/stats")
async def cmd_stats(message: Message):
    """Статистика сохранённых сообщений"""
    if message.from_user.id != ADMIN_ID:
        return
    
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        count = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(DISTINCT chat_id) FROM messages")
        chats = (await cursor.fetchone())[0]
    
    await message.answer(
        f"📊 <b>Статистика:</b>\n\n"
        f"💬 Сохранено сообщений: <b>{count}</b>\n"
        f"👥 Уникальных чатов: <b>{chats}</b>",
        parse_mode=ParseMode.HTML
    )


# ========== ЗАПУСК ==========
async def main():
    await init_db()
    print("🚀 Бот запущен!")
    print(f"👤 Admin ID: {ADMIN_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
