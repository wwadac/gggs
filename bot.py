from aiogram.types.business_connection import BusinessConnection
import asyncio
import logging
from io import BytesIO
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    PhotoSize,
    Video,
    VideoNote,
    Document,
    BufferedInputFile,
    BusinessMessagesDeleted
)
from aiogram.filters import CommandStart, Command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8316728730:AAEMrNJN8O7Efbk7TIDPphqGy5-4VrnigN8"
ADMIN_ID = 8593061718

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище сообщений для отслеживания удалений/изменений
# {chat_id: {message_id: {"text": str, "user": str, "user_id": int, "time": datetime, "media_type": str}}}
messages_cache = {}
MAX_CACHE_PER_CHAT = 500


def get_user_tag(user) -> str:
    """Получить @username или ID"""
    if user.username:
        return f"@{user.username}"
    return f"id:{user.id}"


def cache_message(message: Message):
    """Сохранить сообщение в кэш"""
    chat_id = message.chat.id
    msg_id = message.message_id
    
    if chat_id not in messages_cache:
        messages_cache[chat_id] = {}
    
    # Определяем тип контента
    content = message.text or message.caption or ""
    media_type = None
    
    if message.photo:
        media_type = "фото"
    elif message.video:
        media_type = "видео"
    elif message.video_note:
        media_type = "кружок"
    elif message.document:
        media_type = "документ"
    elif message.voice:
        media_type = "голосовое"
    elif message.audio:
        media_type = "аудио"
    elif message.sticker:
        media_type = "стикер"
    
    messages_cache[chat_id][msg_id] = {
        "text": content,
        "user": get_user_tag(message.from_user),
        "user_id": message.from_user.id,
        "name": message.from_user.first_name,
        "time": datetime.now(),
        "media_type": media_type,
        "file_id": get_file_id(message)
    }
    
    # Чистим старые записи
    if len(messages_cache[chat_id]) > MAX_CACHE_PER_CHAT:
        oldest = sorted(messages_cache[chat_id].keys())[:100]
        for k in oldest:
            del messages_cache[chat_id][k]


def get_file_id(message: Message) -> str | None:
    """Получить file_id медиа"""
    if message.photo:
        return message.photo[-1].file_id
    elif message.video:
        return message.video.file_id
    elif message.video_note:
        return message.video_note.file_id
    elif message.document:
        return message.document.file_id
    elif message.voice:
        return message.voice.file_id
    elif message.audio:
        return message.audio.file_id
    return None


@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🔒 <b>Бот мониторинга</b>\n\n"
        "• Сохраняет удалённые сообщения\n"
        "• Сохраняет изменённые сообщения\n"
        "• Сохраняет одноразки по ответу",
        parse_mode="HTML"
    )


# ========== УДАЛЁННЫЕ СООБЩЕНИЯ ==========
@dp.deleted_business_messages()
async def handle_deleted(event: BusinessMessagesDeleted):
    """Обработка удалённых сообщений"""
    try:
        chat_id = event.chat.id
        deleted_ids = event.message_ids
        
        for msg_id in deleted_ids:
            cached = messages_cache.get(chat_id, {}).get(msg_id)
            
            if cached:
                # Формируем отчёт
                time_sent = cached["time"].strftime("%d.%m %H:%M:%S")
                
                text = f"🗑 <b>УДАЛЕНО</b>\n"
                text += f"👤 {cached['user']}\n"
                text += f"⏰ {time_sent}\n"
                
                if cached["media_type"]:
                    text += f"📎 {cached['media_type']}\n"
                
                if cached["text"]:
                    text += f"💬 {cached['text'][:500]}"
                
                await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
                
                # Если было медиа, пересылаем
                if cached["file_id"]:
                    await send_cached_media(ADMIN_ID, cached)
                
                # Удаляем из кэша
                del messages_cache[chat_id][msg_id]
            else:
                # Сообщение не в кэше (старое)
                await bot.send_message(
                    ADMIN_ID,
                    f"🗑 <b>УДАЛЕНО</b>\n"
                    f"💬 msg_id: {msg_id}\n"
                    f"📍 chat: {event.chat.title or chat_id}\n"
                    f"⚠️ не в кэше",
                    parse_mode="HTML"
                )
                
    except Exception as e:
        logger.error(f"Ошибка deleted: {e}", exc_info=True)


# ========== ИЗМЕНЁННЫЕ СООБЩЕНИЯ ==========
@dp.edited_business_message()
async def handle_edited(message: Message):
    """Обработка изменённых сообщений"""
    try:
        chat_id = message.chat.id
        msg_id = message.message_id
        
        cached = messages_cache.get(chat_id, {}).get(msg_id)
        old_text = cached["text"] if cached else "[не в кэше]"
        new_text = message.text or message.caption or ""
        
        text = f"✏️ <b>ИЗМЕНЕНО</b>\n"
        text += f"👤 {get_user_tag(message.from_user)}\n"
        text += f"📝 <b>Было:</b> {old_text[:300]}\n"
        text += f"📝 <b>Стало:</b> {new_text[:300]}"
        
        await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        
        # Обновляем кэш
        cache_message(message)
        
    except Exception as e:
        logger.error(f"Ошибка edited: {e}", exc_info=True)


# ========== ВСЕ БИЗНЕС СООБЩЕНИЯ (кэширование) ==========
@dp.business_message()
async def handle_all_business(message: Message):
    """Кэшируем все входящие сообщения"""
    cache_message(message)
    logger.info(f"📩 {get_user_tag(message.from_user)}: {message.text or '[медиа]'}")


# ========== ОТВЕТ НА СООБЩЕНИЕ (сохранение одноразок) ==========
@dp.business_message(F.reply_to_message)
async def handle_reply(message: Message):
    """Сохранение по ответу"""
    try:
        conn = await bot.get_business_connection(message.business_connection_id)
        
        if message.from_user.id != conn.user.id:
            cache_message(message)
            return
        
        target = message.reply_to_message
        user_tag = get_user_tag(target.from_user)
        
        file_data = None
        filename = None
        
        if target.photo:
            file_data, filename = await download_media(target.photo[-1].file_id, "photo", "jpg")
        elif target.video:
            file_data, filename = await download_media(target.video.file_id, "video", "mp4")
        elif target.video_note:
            file_data, filename = await download_media(target.video_note.file_id, "videonote", "mp4")
        elif target.document:
            file_data, filename = await download_media(target.document.file_id, "doc", target.document.file_name)
        elif target.text:
            await bot.send_message(
                ADMIN_ID,
                f"💬 {user_tag}\n{target.text}",
                parse_mode="HTML"
            )
            return
        
        if file_data:
            caption = f"📨 {user_tag}"
            if target.caption:
                caption += f"\n{target.caption[:200]}"
            
            await send_media(ADMIN_ID, file_data, filename, caption, target)
            
    except Exception as e:
        logger.error(f"Ошибка reply: {e}", exc_info=True)


async def download_media(file_id: str, prefix: str, ext: str) -> tuple[BytesIO, str]:
    """Скачать медиа по file_id"""
    file_info = await bot.get_file(file_id)
    file_data = BytesIO()
    await bot.download_file(file_info.file_path, file_data)
    file_data.seek(0)
    filename = f"{prefix}_{datetime.now().strftime('%H%M%S')}.{ext}" if not ext.count('.') else ext
    return file_data, filename


async def send_media(chat_id: int, file_data: BytesIO, filename: str, caption: str, original: Message = None):
    """Отправить медиа"""
    try:
        input_file = BufferedInputFile(file_data.getvalue(), filename=filename)
        fn = filename.lower()
        
        if fn.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            await bot.send_photo(chat_id, input_file, caption=caption[:1024], parse_mode="HTML")
        elif fn.endswith('.mp4') or 'video' in fn:
            if 'videonote' in fn:
                await bot.send_video_note(chat_id, input_file)
            else:
                await bot.send_video(chat_id, input_file, caption=caption[:1024], parse_mode="HTML")
        else:
            await bot.send_document(chat_id, input_file, caption=caption[:1024], parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")


async def send_cached_media(chat_id: int, cached: dict):
    """Отправить медиа из кэша по file_id"""
    try:
        file_id = cached.get("file_id")
        if not file_id:
            return
            
        media_type = cached.get("media_type")
        
        if media_type == "фото":
            await bot.send_photo(chat_id, file_id)
        elif media_type == "видео":
            await bot.send_video(chat_id, file_id)
        elif media_type == "кружок":
            await bot.send_video_note(chat_id, file_id)
        elif media_type == "документ":
            await bot.send_document(chat_id, file_id)
        elif media_type == "голосовое":
            await bot.send_voice(chat_id, file_id)
        elif media_type == "аудио":
            await bot.send_audio(chat_id, file_id)
            
    except Exception as e:
        logger.error(f"Ошибка send_cached: {e}")


@dp.message(Command("cache"))
async def cmd_cache(message: Message):
    """Инфо о кэше"""
    if message.from_user.id != ADMIN_ID:
        return
    
    total = sum(len(v) for v in messages_cache.values())
    chats = len(messages_cache)
    
    await message.answer(f"📊 Кэш: {total} сообщений в {chats} чатах")


async def main():
    me = await bot.get_me()
    logger.info(f"🚀 @{me.username} запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
