from aiogram.types.business_connection import BusinessConnection
import asyncio
import logging
from io import BytesIO
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    PhotoSize,
    Video,
    VideoNote,
    BufferedInputFile
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

token = "8316728730:AAEMrNJN8O7Efbk7TIDPphqGy5-4VrnigN8" # <-- ВАШ ТОКЕН
if not token:
    logger.error("Переменная токена не задана!")
    exit(1)

bot = Bot(token=token)
dp = Dispatcher()

@dp.business_message(F.reply_to_message)
async def handle_business_media(business_message: Message):
    try:
        business_conn: BusinessConnection = await bot.get_business_connection(
            business_message.business_connection_id
        )

        if not business_message.from_user.id == business_conn.user.id:
            return
        
        target_message = business_message.reply_to_message
        
        file_data = None
        filename = None
        caption = None
        
        if target_message.photo:
            file_data, filename = await download_photo(target_message.photo)
            caption = f" Фото {business_message.from_user.first_name}"
            
        elif target_message.video:
            file_data, filename = await download_video(target_message.video)
            caption = f" Видео {business_message.from_user.first_name}"
            
        elif target_message.video_note:
            file_data, filename = await download_video_note(target_message.video_note)
            caption = f" Кружок {business_message.from_user.first_name}"
        
        if file_data and filename:
            if target_message.caption:
                caption += f"\n\n Подпись: {target_message.caption}"
            
            await send_to_owner(
                business_conn.user.id,
                file_data,
                filename,
                caption
            )
                    
    except Exception as e:
        logger.error(f"Ошибка при обработке медиа: {e}")


async def download_photo(photos: list[PhotoSize]) -> tuple[BytesIO, str]:   
    file_info = await bot.get_file(photos[-1].file_id)
    file_data = BytesIO()
    await bot.download_file(file_info.file_path, file_data)
    file_data.seek(0)
    
    filename = f"photo_{photos[-1].file_id}.jpg"
    return file_data, filename


async def download_video(video: Video) -> tuple[BytesIO, str]:
    file_info = await bot.get_file(video.file_id)
    file_data = BytesIO()
    await bot.download_file(file_info.file_path, file_data)
    file_data.seek(0)
    
    filename = video.file_name or f"video_{video.file_id}.mp4"
    return file_data, filename


async def download_video_note(video_note: VideoNote) -> tuple[BytesIO, str]:
    file_info = await bot.get_file(video_note.file_id)
    file_data = BytesIO()
    await bot.download_file(file_info.file_path, file_data)
    file_data.seek(0)
    
    filename = f"video_note_{video_note.file_id}.mp4"
    return file_data, filename


async def send_to_owner(
    owner_id: int,
    file_data: BytesIO,
    filename: str,
    caption: str
):
    try:
        input_file = BufferedInputFile(file_data.read(), filename=filename)
        
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            await bot.send_photo(
                chat_id=owner_id,
                photo=input_file,
                caption=caption
            )
        elif 'video_note' in filename:
            await bot.send_video_note(
                chat_id=owner_id,
                video_note=input_file
            )
            if caption:
                await bot.send_message(owner_id, caption)
        else:
            await bot.send_video(
                chat_id=owner_id,
                video=input_file,
                caption=caption
            )
            
    except Exception as e:
        logger.error(f"Ошибка при отправке: {e}")
        raise


async def main():
    
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    finally:
        await bot.delete_webhook(drop_pending_updates=True)
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
