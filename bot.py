import asyncio
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, BusinessMessagesDeleted
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.filters import Command

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8316728730:AAEMrNJN8O7Efbk7TIDPphqGy5-4VrnigN8"
ADMIN_ID = 8593061718  # Твой Telegram ID
DATABASE = "messages.db"
# ===============================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Словарь для отслеживания ответов на одноразки
temp_messages_to_forward = {}


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
                is_view_once BOOLEAN DEFAULT 0,
                PRIMARY KEY (message_id, chat_id)
            )
        ''')
        await db.commit()


async def save_message(msg: Message, business_connection_id: str = None, is_view_once: bool = False):
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
             first_name, text, caption, file_id, file_type, date, is_view_once)
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
            msg.date.isoformat(),
            1 if is_view_once else 0
        ))
        await db.commit()


async def get_message(chat_id: int, message_id: int):
    """Получение одного сообщения из БД"""
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


async def forward_saved_message(chat_id: int, message_id: int):
    """Пересылка сохраненного сообщения админу в ЛС"""
    msg_data = await get_message(chat_id, message_id)
    
    if not msg_data:
        return
    
    # Формируем информацию о сообщении
    caption = f"👤 <b>От:</b> {msg_data['first_name']} (@{msg_data['username']})\n"
    caption += f"💬 <b>Chat ID:</b> <code>{msg_data['chat_id']}</code>\n"
    
    if msg_data['text']:
        caption += f"\n📝 <b>Текст:</b>\n{msg_data['text']}"
    elif msg_data['caption']:
        caption += f"\n📝 <b>Подпись:</b>\n{msg_data['caption']}"
    
    # Отправляем медиафайл или текст
    try:
        if msg_data['file_type'] == 'photo':
            await bot.send_photo(
                ADMIN_ID, 
                msg_data['file_id'], 
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif msg_data['file_type'] == 'video':
            await bot.send_video(
                ADMIN_ID, 
                msg_data['file_id'], 
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif msg_data['file_type'] == 'document':
            await bot.send_document(
                ADMIN_ID, 
                msg_data['file_id'], 
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif msg_data['file_type'] == 'voice':
            await bot.send_voice(
                ADMIN_ID, 
                msg_data['file_id'], 
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif msg_data['file_type'] == 'video_note':
            await bot.send_video_note(
                ADMIN_ID, 
                msg_data['file_id']
            )
            await bot.send_message(
                ADMIN_ID,
                f"📹 Видеосообщение от @{msg_data['username']}\nChat ID: <code>{msg_data['chat_id']}</code>",
                parse_mode=ParseMode.HTML
            )
        elif msg_data['file_type'] == 'sticker':
            await bot.send_sticker(
                ADMIN_ID, 
                msg_data['file_id']
            )
            await bot.send_message(
                ADMIN_ID,
                f"🩷 Стикер от @{msg_data['username']}\nChat ID: <code>{msg_data['chat_id']}</code>",
                parse_mode=ParseMode.HTML
            )
        elif msg_data['file_type'] == 'audio':
            await bot.send_audio(
                ADMIN_ID, 
                msg_data['file_id'], 
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        else:
            # Если нет файла, отправляем только текст
            await bot.send_message(
                ADMIN_ID,
                f"💬 <b>Сообщение от @{msg_data['username']}</b>\n\n"
                f"Chat ID: <code>{msg_data['chat_id']}</code>\n\n"
                f"📝 <b>Текст:</b>\n{msg_data['text']}",
                parse_mode=ParseMode.HTML
            )
        
        print(f"📤 Переслано сообщение {message_id} от @{msg_data['username']}")
        
    except Exception as e:
        await bot.send_message(
            ADMIN_ID,
            f"⚠️ Ошибка при пересылке сообщения {message_id}: {e}",
            parse_mode=ParseMode.HTML
        )


# ========== ОБРАБОТЧИКИ ==========

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Я бот для сохранения удалённых сообщений.\n\n"
        "📌 <b>Как работает пересылка одноразок:</b>\n"
        "1. Клиент отправляет тебе одноразковое сообщение\n"
        "2. Ты отвечаешь на него ЛЮБЫМ сообщением\n"
        "3. Я сразу присылаю тебе копию этого сообщения в ЛС\n\n"
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
    
    # Проверяем, является ли сообщение одноразковым
    is_view_once = False
    
    if message.has_media_spoiler:
        is_view_once = True
    elif message.photo and getattr(message.photo[-1], 'has_spoiler', False):
        is_view_once = True
    elif message.video and getattr(message.video, 'has_spoiler', False):
        is_view_once = True
    
    # Сохраняем сообщение
    await save_message(message, message.business_connection_id, is_view_once)
    
    if is_view_once:
        print(f"⚠️ Одноразка от @{message.from_user.username} (сохранено)")
    else:
        print(f"💾 Сохранено сообщение от @{message.from_user.username}: {message.text or '[медиа]'}")


@dp.business_message(F.reply_to_message)
async def handle_business_reply(message: Message):
    """Обработка ответов админа на сообщения клиентов"""
    
    # Проверяем, что ответ от админа (тебя)
    if message.from_user.id != ADMIN_ID:
        return
    
    reply_to_msg_id = message.reply_to_message.message_id
    chat_id = message.chat.id
    
    # Проверяем, было ли это сообщение сохранено как одноразка
    msg_data = await get_message(chat_id, reply_to_msg_id)
    
    if msg_data and msg_data['is_view_once']:
        # Пересылаем сообщение админу в ЛС
        await forward_saved_message(chat_id, reply_to_msg_id)
        
        # Отправляем подтверждение в чат
        await message.reply(
            "✅ <b>Одноразка переслана тебе в ЛС!</b>",
            parse_mode=ParseMode.HTML
        )


@dp.edited_business_message()
async def handle_edited_business_message(message: Message):
    """Обработка отредактированных сообщений"""
    
    # Получаем старую версию
    old_msg = await get_message(message.chat.id, message.message_id)
    
    if old_msg:
        await bot.send_message(
            ADMIN_ID,
            f"✏️ <b>Сообщение отредактировано!</b>\n\n"
            f"👤 Клиент: {message.from_user.first_name} (@{message.from_user.username})\n\n"
            f"📝 <b>Было:</b>\n{old_msg['text'] or old_msg['caption'] or '[медиа]'}\n\n"
            f"📝 <b>Стало:</b>\n{message.text or message.caption or '[медиа]'}",
            parse_mode=ParseMode.HTML
        )
    
    # Обновляем в базе
    await save_message(message, message.business_connection_id)


@dp.deleted_business_messages()
async def handle_deleted_messages(event: BusinessMessagesDeleted):
    """Обработка удалённых сообщений"""
    
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
            f"📅 <b>Дата:</b> {msg['date']}\n"
        )
        
        if msg['is_view_once']:
            notification += f"⚠️ <b>Это была одноразка!</b>\n"
        
        # Отправляем контент
        if msg['file_type'] and msg['file_id']:
            notification += f"📎 <b>Тип:</b> {msg['file_type']}\n"
            if text:
                notification += f"📝 <b>Подпись:</b> {text}"
            
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
                    await bot.send_message(ADMIN_ID, "👆 Удалённое видеосообщение")
                elif msg['file_type'] == 'sticker':
                    await bot.send_sticker(ADMIN_ID, msg['file_id'])
                    await bot.send_message(ADMIN_ID, "👆 Удалённый стикер")
                elif msg['file_type'] == 'audio':
                    await bot.send_audio(ADMIN_ID, msg['file_id'], caption="👆 Удалённое аудио")
            except Exception as e:
                await bot.send_message(ADMIN_ID, f"⚠️ Не удалось отправить файл: {e}")
        else:
            notification += f"\n💬 <b>Текст:</b>\n<code>{text}</code>"
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
            "и уведомлять тебя об удалённых.\n\n"
            "<b>Как получить одноразку:</b>\n"
            "1. Клиент отправляет одноразковое сообщение\n"
            "2. Ты отвечаешь на него ЛЮБЫМ сообщением\n"
            "3. Я пришлю копию в этот чат! 🚀",
            parse_mode=ParseMode.HTML
        )
        print(f"✅ Подключён к бизнес-аккаунту: @{connection.user.username}")
    else:
        await bot.send_message(
            connection.user.id,
            "❌ <b>Бот отключён от бизнес-аккаунта.</b>",
            parse_mode=ParseMode.HTML
        )


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика сохранённых сообщений"""
    if message.from_user.id != ADMIN_ID:
        return
    
    async with aiosqlite.connect(DATABASE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        total = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE is_view_once = 1")
        view_once = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(DISTINCT chat_id) FROM messages")
        chats = (await cursor.fetchone())[0]
    
    await message.answer(
        f"📊 <b>Статистика:</b>\n\n"
        f"💬 Всего сообщений: <b>{total}</b>\n"
        f"⚠️ Одноразок: <b>{view_once}</b>\n"
        f"👥 Уникальных чатов: <b>{chats}</b>",
        parse_mode=ParseMode.HTML
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь"""
    await message.answer(
        "🆘 <b>Помощь по боту:</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Начало работы\n"
        "/stats - Статистика\n"
        "/help - Эта справка\n\n"
        "<b>Как получить одноразку:</b>\n"
        "1. Клиент отправляет фото/видео с таймером\n"
        "2. Ты отвечаешь на это сообщение\n"
        "3. Бот присылает копию тебе в ЛС\n\n"
        "<b>Что сохраняется:</b>\n"
        "• Все сообщения от клиентов\n"
        "• Фото/видео с таймером\n"
        "• Удалённые сообщения\n"
        "• Отредактированные сообщения",
        parse_mode=ParseMode.HTML
    )


# ========== ЗАПУСК ==========
async def main():
    await init_db()
    print("🚀 Бот запущен!")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("\n📌 Инструкция по использованию:")
    print("1. Клиент отправляет тебе фото/видео с таймером")
    print("2. Ты отвечаешь на это сообщение (любой текст)")
    print("3. Бот пришлёт копию в ЛС")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
