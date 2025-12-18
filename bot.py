import asyncio
import aiosqlite
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, BusinessMessagesDeleted
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8316728730:AAEMrNJN8O7Efbk7TIDPphqGy5-4VrnigN8"
ADMIN_ID = 8593061718  # Твой Telegram ID
DATABASE = "messages.db"
# ===============================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Кэш для отслеживания пересланных сообщений
forwarded_messages = set()


# ========== БАЗА ДАННЫХ ==========
async def init_db():
    """Создание таблиц в БД"""
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                is_view_once INTEGER DEFAULT 0,
                UNIQUE(message_id, chat_id, business_connection_id)
            )
        ''')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_chat_message ON messages(chat_id, message_id)')
        await db.commit()


async def save_message(msg: Message, business_connection_id: str = None, is_view_once: bool = False):
    """Сохранение сообщения в БД"""
    
    # Определяем тип файла
    file_id = None
    file_type = None
    
    if msg.photo:
        file_id = msg.photo[-1].file_id
        file_type = "photo"
        # Проверяем, является ли фото одноразкой
        if hasattr(msg, 'has_media_spoiler') and msg.has_media_spoiler:
            is_view_once = True
    elif msg.video:
        file_id = msg.video.file_id
        file_type = "video"
        if hasattr(msg, 'has_media_spoiler') and msg.has_media_spoiler:
            is_view_once = True
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
    
    # Логируем для отладки
    logger.info(f"Сохранение сообщения {msg.message_id} от @{msg.from_user.username if msg.from_user else 'N/A'} "
                f"тип: {file_type}, одноразка: {is_view_once}")
    
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


async def forward_to_admin(chat_id: int, message_id: int, msg_data: dict = None):
    """Пересылка сообщения админу"""
    
    if not msg_data:
        msg_data = await get_message(chat_id, message_id)
    
    if not msg_data:
        logger.warning(f"Сообщение {message_id} в чате {chat_id} не найдено в БД")
        return False
    
    # Проверяем, не пересылали ли уже
    cache_key = f"{chat_id}_{message_id}"
    if cache_key in forwarded_messages:
        return True
    
    try:
        caption = f"👤 От: {msg_data['first_name']} (@{msg_data['username']})\n"
        caption += f"💬 Chat ID: {msg_data['chat_id']}\n"
        
        if msg_data['text']:
            caption += f"\n📝 Текст:\n{msg_data['text']}"
        elif msg_data['caption']:
            caption += f"\n📝 Подпись:\n{msg_data['caption']}"
        
        # Если это одноразка, добавляем пометку
        if msg_data['is_view_once']:
            caption += "\n\n⚠️ ОДНОРАЗОВОЕ СООБЩЕНИЕ!"
        
        # Отправляем медиа или текст
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
            await bot.send_video_note(ADMIN_ID, msg_data['file_id'])
            await bot.send_message(ADMIN_ID, f"📹 Видеосообщение от @{msg_data['username']}")
        elif msg_data['file_type'] == 'sticker':
            await bot.send_sticker(ADMIN_ID, msg_data['file_id'])
            await bot.send_message(ADMIN_ID, f"🩷 Стикер от @{msg_data['username']}")
        elif msg_data['file_type'] == 'audio':
            await bot.send_audio(ADMIN_ID, msg_data['file_id'], caption=caption)
        else:
            # Текстовое сообщение
            await bot.send_message(
                ADMIN_ID,
                f"💬 Сообщение от @{msg_data['username']}\n\n"
                f"Chat ID: {msg_data['chat_id']}\n\n"
                f"📝 Текст:\n{msg_data['text']}",
                parse_mode=ParseMode.HTML
            )
        
        # Добавляем в кэш
        forwarded_messages.add(cache_key)
        logger.info(f"Переслано сообщение {message_id} от @{msg_data['username']}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при пересылке: {e}")
        await bot.send_message(ADMIN_ID, f"❌ Ошибка при пересылке: {e}")
        return False


# ========== ОБРАБОТЧИКИ ==========

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    await message.answer(
        "👋 <b>Привет! Я бот для сохранения одноразок.</b>\n\n"
        "<b>Как использовать:</b>\n"
        "1. Подключи меня к бизнес-аккаунту\n"
        "2. Клиент отправит фото/видео с таймером\n"
        "3. Ответь на это сообщение ЛЮБЫМ текстом\n"
        "4. Я пришлю тебе копию в этот чат!\n\n"
        "<b>Команды:</b>\n"
        "/stats - статистика\n"
        "/test - тестовая отправка\n"
        "/help - помощь",
        parse_mode=ParseMode.HTML
    )


@dp.message(Command("test"))
async def cmd_test(message: Message):
    """Тестовая команда"""
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer("✅ Бот работает!")
    await bot.send_message(ADMIN_ID, "✅ Тестовое сообщение в ЛС")


@dp.business_message()
async def handle_business_message(message: Message):
    """Обработка бизнес-сообщений от клиентов"""
    logger.info(f"Получено бизнес-сообщение: {message.message_id} от {message.from_user.username}")
    
    # Логируем все атрибуты для отладки
    logger.info(f"Атрибуты сообщения: {dir(message)}")
    
    # Сохраняем сообщение
    is_view_once = False
    
    # Проверяем разными способами
    if hasattr(message, 'has_media_spoiler') and message.has_media_spoiler:
        is_view_once = True
        logger.info(f"Обнаружена одноразка по has_media_spoiler")
    
    # Также проверяем в медиа
    if message.photo and hasattr(message.photo[-1], 'has_spoiler') and message.photo[-1].has_spoiler:
        is_view_once = True
        logger.info(f"Обнаружена одноразка по has_spoiler в фото")
    
    if message.video and hasattr(message.video, 'has_spoiler') and message.video.has_spoiler:
        is_view_once = True
        logger.info(f"Обнаружена одноразка по has_spoiler в видео")
    
    # Сохраняем в базу
    business_connection_id = getattr(message, 'business_connection_id', None)
    await save_message(message, business_connection_id, is_view_once)
    
    if is_view_once:
        logger.info(f"⚠️ Сохранена одноразка от @{message.from_user.username}")


@dp.message(F.reply_to_message)
async def handle_reply_to_message(message: Message):
    """Обработка ВСЕХ ответов на сообщения"""
    
    # Проверяем, что это ответ в бизнес-чате
    if not hasattr(message, 'business_connection_id') or not message.business_connection_id:
        return
    
    # Проверяем, что отвечаем мы (админ)
    if message.from_user.id != ADMIN_ID:
        return
    
    reply_to = message.reply_to_message
    if not reply_to:
        return
    
    logger.info(f"Админ ответил на сообщение {reply_to.message_id}")
    
    # Получаем сообщение из БД
    msg_data = await get_message(message.chat.id, reply_to.message_id)
    
    if not msg_data:
        await message.reply("❌ Сообщение не найдено в базе данных")
        return
    
    # Пересылаем ВСЕ сообщения, на которые ответил админ
    success = await forward_to_admin(message.chat.id, reply_to.message_id, msg_data)
    
    if success:
        await message.reply("✅ Сообщение переслано тебе в ЛС!")
    else:
        await message.reply("❌ Не удалось переслать сообщение")


@dp.message(Command("get"))
async def cmd_get_last(message: Message):
    """Получить последнее сообщение из БД"""
    if message.from_user.id != ADMIN_ID:
        return
    
    async with aiosqlite.connect(DATABASE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT * FROM messages 
            ORDER BY date DESC LIMIT 1
        ''')
        last_msg = await cursor.fetchone()
    
    if last_msg:
        info = (f"📊 Последнее сообщение:\n"
                f"ID: {last_msg['message_id']}\n"
                f"От: @{last_msg['username']}\n"
                f"Тип: {last_msg['file_type']}\n"
                f"Одноразка: {'Да' if last_msg['is_view_once'] else 'Нет'}")
        await message.answer(info)
        
        # Пробуем переслать
        await forward_to_admin(last_msg['chat_id'], last_msg['message_id'], last_msg)
    else:
        await message.answer("📭 В базе нет сообщений")


@dp.message(Command("debug"))
async def cmd_debug(message: Message):
    """Отладочная информация"""
    if message.from_user.id != ADMIN_ID:
        return
    
    debug_info = f"""
    🤖 <b>Отладочная информация:</b>
    
    👤 Admin ID: {ADMIN_ID}
    💾 Сообщений в кэше: {len(forwarded_messages)}
    🗃 Бот работает: Да
    📊 Последние 5 сообщений в кэше: {list(forwarded_messages)[-5:]}
    """
    
    await message.answer(debug_info, parse_mode=ParseMode.HTML)


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    """Очистка кэша"""
    if message.from_user.id != ADMIN_ID:
        return
    
    forwarded_messages.clear()
    await message.answer("✅ Кэш очищен")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь"""
    help_text = """
    🆘 <b>Помощь:</b>
    
    <b>Как получить одноразку:</b>
    1. Клиент отправляет фото/видео с таймером
    2. Ты отвечаешь на это сообщение ЛЮБЫМ текстом
    3. Бот присылает копию тебе в ЛС
    
    <b>Команды:</b>
    /start - Начало работы
    /test - Проверить работу бота
    /get - Получить последнее сообщение
    /debug - Отладочная информация
    /clear - Очистить кэш
    /help - Эта справка
    
    <b>Если не работает:</b>
    1. Убедись, что бот подключен к бизнес-аккаунту
    2. Проверь ID админа в настройках
    3. Попробуй команду /test
    """
    await message.answer(help_text, parse_mode=ParseMode.HTML)


# ========== ЗАПУСК ==========
async def main():
    await init_db()
    
    me = await bot.get_me()
    logger.info(f"🚀 Бот запущен: @{me.username}")
    logger.info(f"👤 Admin ID: {ADMIN_ID}")
    logger.info(f"📊 Используй команду /start для инструкций")
    
    # Очищаем вебхук (на всякий случай)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем поллинг
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
