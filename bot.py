import asyncio
import logging
import os
import re
import secrets
import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv


load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("yuklanadi_bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MAX_DOWNLOAD_BYTES = int(os.getenv("MAX_DOWNLOAD_MB", "48")) * 1024 * 1024
MAX_ITEMS_PER_LINK = max(1, int(os.getenv("MAX_ITEMS_PER_LINK", "10")))
DOWNLOAD_TIMEOUT = max(60, int(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "600")))
PENDING_TTL_SECONDS = 30 * 60
URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)

# A short-lived in-memory store is enough: the URL is never put into callback_data,
# and a restart simply expires old buttons.
pending_links: dict[str, tuple[int, str, float]] = {}
download_slots = asyncio.Semaphore(2)


def trim_url(raw_url: str) -> str:
    return raw_url.rstrip(".,!?;:)]}\"'")


def is_valid_public_url(raw_url: str) -> bool:
    try:
        parsed = urlparse(raw_url)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    blocked_hosts = {"localhost", "localhost.localdomain", "0.0.0.0", "::1"}
    if host in blocked_hosts or host.endswith(".local"):
        return False
    # Reject literal private/link-local IPv4 addresses. Domain names are left
    # to the extractor; this is not intended to be a full network firewall.
    parts = host.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        numbers = [int(part) for part in parts]
        if (
            numbers[0] == 10
            or numbers[0] == 127
            or (numbers[0] == 192 and numbers[1] == 168)
            or (numbers[0] == 172 and 16 <= numbers[1] <= 31)
            or (numbers[0] == 169 and numbers[1] == 254)
        ):
            return False
    return True


def cleanup_pending() -> None:
    now = time.time()
    expired = [key for key, (_, _, expires) in pending_links.items() if expires < now]
    for key in expired:
        pending_links.pop(key, None)


def remember_link(user_id: int, url: str) -> str:
    cleanup_pending()
    token = secrets.token_urlsafe(8)
    pending_links[token] = (user_id, url, time.time() + PENDING_TTL_SECONDS)
    return token


def media_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Video", callback_data=f"get:video:{token}"),
                InlineKeyboardButton(text="🎵 Audio MP3", callback_data=f"get:audio:{token}"),
            ],
            [
                InlineKeyboardButton(text="🖼 Rasm / fayl", callback_data=f"get:image:{token}"),
            ],
        ]
    )


def format_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "login" in text or "authentication" in text or "private" in text:
        return (
            "Bu havola login yoki private kontent talab qildi. "
            "Bot faqat ochiq/public kontent bilan ishlaydi."
        )
    if "sign in" in text or "confirm you are human" in text:
        return "Platforma ushbu so‘rovni chekladi. Public boshqa havolani sinab ko‘ring."
    if "too large" in text or "max_filesize" in text:
        return (
            "Fayl Telegram bot limiti uchun juda katta. "
            "Audio formatini yoki pastroq sifatli manbani tanlang."
        )
    if "timed out" in text or "timeout" in text:
        return "Yuklab olish vaqti tugadi. Havolani yoki kichikroq videoni qayta sinab ko‘ring."
    return "Media yuklanmadi. Havola ochiq ekanini tekshirib, yana bir marta yuboring."


def progress_hook(data: dict) -> None:
    if data.get("status") == "downloading":
        downloaded = data.get("downloaded_bytes", 0)
        if downloaded > MAX_DOWNLOAD_BYTES:
            raise yt_dlp.utils.DownloadError("too large")


def download_media(url: str, kind: str, destination: str) -> list[Path]:
    output_template = str(Path(destination) / "%(title).120B [%(id)s].%(ext)s")
    common = {
        "outtmpl": output_template,
        "noplaylist": True,
        "max_filesize": MAX_DOWNLOAD_BYTES,
        "progress_hooks": [progress_hook],
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
        "ignoreerrors": False,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "windowsfilenames": True,
    }

    if kind == "audio":
        common.update(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        )
    elif kind == "image":
        common.update(
            {
                "format": "best[ext=jpg]/best[ext=jpeg]/best[ext=png]/best",
            }
        )
    else:
        # 720p keeps ordinary downloads usable within Telegram's bot limit.
        common.update(
            {
                "format": (
                    "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/"
                    "best[height<=720][ext=mp4]/best[ext=mp4]/best"
                ),
                "merge_output_format": "mp4",
            }
        )

    with yt_dlp.YoutubeDL(common) as downloader:
        downloader.download([url])

    files = [
        path
        for path in Path(destination).iterdir()
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    files.sort(key=lambda path: path.stat().st_mtime)
    if not files:
        raise yt_dlp.utils.DownloadError("no files")

    # FFmpeg can increase an output slightly after the initial download.
    valid_files = []
    for path in files:
        if path.stat().st_size > MAX_DOWNLOAD_BYTES:
            path.unlink(missing_ok=True)
        else:
            valid_files.append(path)
    if not valid_files:
        raise yt_dlp.utils.DownloadError("too large")
    return valid_files[:MAX_ITEMS_PER_LINK]


async def send_downloaded_media(message: Message, files: list[Path], kind: str) -> None:
    for path in files:
        caption = f"YUKLANADI_BOT • {path.name[:800]}"
        if kind == "audio" or path.suffix.lower() in {".mp3", ".m4a", ".ogg", ".wav"}:
            await message.answer_audio(
                audio=FSInputFile(path),
                caption=caption,
                title=path.stem[:64],
            )
        elif kind == "image" and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            try:
                await message.answer_photo(photo=FSInputFile(path), caption=caption)
            except TelegramBadRequest:
                await message.answer_document(document=FSInputFile(path), caption=caption)
        else:
            await message.answer_video(
                video=FSInputFile(path),
                caption=caption,
                supports_streaming=True,
            )


async def run_download(message: Message, url: str, kind: str) -> None:
    label = {"video": "video", "audio": "audio", "image": "rasm/fayl"}[kind]
    status = await message.answer(f"⏳ {label.capitalize()} tayyorlanmoqda…")
    await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)
    temp_dir = tempfile.mkdtemp(prefix="yuklanadi_")
    try:
        async with download_slots:
            files = await asyncio.wait_for(
                asyncio.to_thread(download_media, url, kind, temp_dir),
                timeout=DOWNLOAD_TIMEOUT,
            )
        await status.edit_text("✅ Tayyor. Telegramga yuboryapman…")
        await send_downloaded_media(message, files, kind)
        await status.delete()
    except asyncio.TimeoutError:
        await status.edit_text("⌛ Yuklash vaqti tugadi. Kichikroq yoki boshqa public havolani sinab ko‘ring.")
    except Exception as exc:
        logger.warning("Download failed for %s: %s", url, exc)
        await status.edit_text(f"❌ {format_error(exc)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "👋 <b>YUKLANADI_BOT</b>\n\n"
        "Telegram, Instagram, YouTube, TikTok, Facebook, X/Twitter va "
        "yt-dlp qo‘llaydigan boshqa public platforma linkini yuboring.\n\n"
        "Keyin kerakli formatni tanlang: video, MP3 audio yoki rasm/fayl.\n\n"
        "🔒 Private/login talab qiladigan kontent yuklanmaydi.\n"
        "📌 Mualliflik huquqi va platforma qoidalariga rioya qiling.",
    )


@dp.message(F.text)
async def link_handler(message: Message) -> None:
    raw_text = message.text or ""
    matches = URL_RE.findall(raw_text)
    if not matches:
        await message.answer("Link yuboring — masalan: https://youtube.com/watch?v=...")
        return
    url = trim_url(matches[0])
    if not is_valid_public_url(url):
        await message.answer("Iltimos, faqat ochiq http/https havola yuboring.")
        return
    token = remember_link(message.from_user.id, url)
    await message.answer(
        "Formatni tanlang. Eski tugmalar 30 daqiqadan keyin ishlamaydi.",
        reply_markup=media_keyboard(token),
    )


@dp.callback_query(F.data.startswith("get:"))
async def download_callback(callback: CallbackQuery) -> None:
    try:
        _, kind, token = (callback.data or "").split(":", 2)
    except ValueError:
        await callback.answer("Tugma eskirgan.", show_alert=True)
        return
    record = pending_links.get(token)
    if not record:
        await callback.answer("Bu tugma eskirgan. Linkni qayta yuboring.", show_alert=True)
        return
    owner_id, url, expires = record
    if owner_id != callback.from_user.id or expires < time.time():
        await callback.answer("Bu tugma faqat link yuborgan foydalanuvchi uchun.", show_alert=True)
        return
    if kind not in {"video", "audio", "image"}:
        await callback.answer("Noma’lum format.", show_alert=True)
        return
    pending_links.pop(token, None)
    await callback.answer("Yuklash boshlandi")
    if callback.message:
        await run_download(callback.message, url, kind)


async def main() -> None:
    if not BOT_TOKEN or "PASTE_YOUR" in BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. .env fayliga @BotFather bergan tokenni yozing."
        )
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("YUKLANADI_BOT ishga tushmoqda")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, TelegramNetworkError):
        logger.info("Bot to‘xtatildi")