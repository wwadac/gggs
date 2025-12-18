import asyncio
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8316728730:AAEMrNJN8O7Efbk7TIDPphqGy5-4VrnigN8"  # Замени на свой токен
ADMIN_ID = 8593061718  # Замени на свой ID
SAVE_DIR = "saved_media"  # ← Вот эта строка была пропущена!
# ===============================

# Создаём папку для сохранения
os.makedirs(SAVE_DIR, exist_ok=True)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.business_message(F.photo | F.video | F.video_note | F.voice | F.animation)
async def save_all_media(message: Message):
    """Сохраняет ВСЕ медиа от клиентов (включая одноразки)"""
    
    user = message.from_user
    user_info = f"{user.first_name}"
    if user.username:
        user_info += f" (@{user.username})"
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        if message.photo:
            file = await bot.get_file(message.photo[-1].file_id)
            ext = "jpg"
            media_type = "🖼 Фото"
            
        elif message.video:
            file = await bot.get_file(message.video.file_id)
            ext = "mp4"
            media_type = "🎥 Видео"
            
        elif message.video_note:
            file = await bot.get_file(message.video_note.file_id)
            ext = "mp4"
            media_type = "⚫ Кружок"
            
        elif message.voice:
            file = await bot.get_file(message.voice.file_id)
            ext = "ogg"
            media_type = "🎤 Голосовое"
            
        elif message.animation:
            file = await bot.get_file(message.animation.file_id)
            ext = "mp4"
            media_type = "🎬 GIF"
        else:
            return
        
        # Скачиваем файл
        filename = f"{SAVE_DIR}/{user.id}_{timestamp}.{ext}"
        await bot.download_file(file.file_path, filename)
        
        # Уведомление
        caption = (
            f"💾 <b>Сохранено!</b>\n\n"
            f"👤 <b>От:</b> {user_info}\n"
            f"🆔 <code>{user.id}</code>\n"
            f"📎 <b>Тип:</b> {media_type}\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        
        if message.caption:
            caption += f"\n📝 <b>Подпись:</b> {message.caption}"
        
        # Отправляем админу
        if message.photo:
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif message.video:
            await bot.send_video(ADMIN_ID, message.video.file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif message.video_note:
            await bot.send_message(ADMIN_ID, caption, parse_mode=ParseMode.HTML)
            await bot.send_video_note(ADMIN_ID, message.video_note.file_id)
        elif message.voice:
            await bot.send_voice(ADMIN_ID, message.voice.file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif message.animation:
            await bot.send_animation(ADMIN_ID, message.animation.file_id, caption=caption, parse_mode=ParseMode.HTML)
        
        print(f"✅ Сохранено {media_type} от {user_info}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        await bot.send_message(
            ADMIN_ID,
            f"⚠️ Не удалось сохранить медиа от {user_info}\nОшибка: {e}",
            parse_mode=ParseMode.HTML
        )


@dp.business_message(F.text)
async def save_text(message: Message):
    """Сохраняет текстовые сообщения"""
    user = message.from_user
    print(f"💬 {user.first_name}: {message.text[:50]}...")


@dp.business_connection()
async def on_connect(connection):
    if connection.is_enabled:
        await bot.send_message(
            connection.user.id,
            "✅ <b>Бот подключён!</b>\n\nТеперь все медиа от клиентов будут сохраняться.",
            parse_mode=ParseMode.HTML
        )


async def main():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
