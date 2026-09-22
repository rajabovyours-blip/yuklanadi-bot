# YUKLANADI_BOT

Telegram bot: foydalanuvchi public video, rasm yoki audio linkini yuboradi, formatni tanlaydi va bot faylni Telegramga qaytaradi.

## Qo‘llab-quvvatlash

Yuklash qismi `yt-dlp` orqali ishlaydi. Shuning uchun YouTube, Instagram, TikTok, Facebook, X/Twitter, Reddit, SoundCloud va `yt-dlp` ro‘yxatidagi ko‘plab boshqa saytlar ishlaydi. Platformalar tez-tez o‘zgaradi; ayrim linklar vaqtincha ishlamasligi mumkin.

Bot:

- faqat ochiq/public linklar bilan ishlaydi;
- login, private profil, DRM yoki paywall cheklovlarini chetlab o‘tmaydi;
- Telegram bot upload limitiga mos ravishda odatda 48 MB gacha yuklaydi;
- video uchun 720p gacha bo‘lgan variantni tanlaydi;
- audio uchun MP3 yaratadi;
- Instagram carousel yoki playlistga o‘xshash javoblarni ko‘pi bilan 10 ta faylgacha yuboradi;
- bir vaqtda 2 ta yuklashni bajaradi.

Media faqat vaqtinchalik papkaga yoziladi va yuborilgach o‘chiriladi.

## 1. Telegram token olish

1. Telegramda `@BotFather` ni oching.
2. `/newbot` yuboring.
3. Bot nomini, masalan, `YUKLANADI` deb kiriting.
4. Username oxirida `_bot` bo‘lsin, masalan `YUKLANADI_BOT`.
5. BotFather bergan tokenni nusxalang.

Tokenni GitHub kodiga qo‘ymang. Railway Variables bo‘limiga qo‘ying.

## 2. GitHub’ga telefondan joylash

### Eng oson usul: brauzer orqali

1. GitHub ilovasida yoki telefon brauzerida yangi repository yarating. Masalan: `yuklanadi-bot`.
2. Ushbu ZIP ichidagi fayllarni oching.
3. Repository ichidan **Add file → Upload files** ni tanlang.
4. `bot.py`, `Dockerfile`, `railway.json`, `requirements.txt`, `.gitignore`, `.dockerignore`, `.env.example` va `README.md` fayllarini yuklang.
5. **Commit changes** ni bosing.

`.env` faylini GitHub’ga yuklamang.

### ZIP ochilmasa

GitHub brauzer yuklash oynasi ZIP ichidagi fayllarni bevosita repository root'iga joylay olmaydi. Telefoningizdagi Files/ZArchiver kabi arxiv dasturida avval ZIP'ni oching, keyin ichidagi fayllarni tanlab GitHub'ga yuklang. Repository ichida `bot.py` to‘g‘ridan-to‘g‘ri asosiy papkada turishi kerak, masalan:

```text
yuklanadi-bot/
├── bot.py
├── Dockerfile
├── railway.json
└── requirements.txt
```

## 3. Railway’ga telefondan deploy

1. Telefon brauzerida [railway.app](https://railway.app) ga kiring va GitHub bilan login qiling.
2. **New Project → Deploy from GitHub repo** ni bosing.
3. `yuklanadi-bot` repository'sini tanlang.
4. Railway Dockerfile'ni avtomatik topadi. Build tugashini kuting.
5. Project ichida bot service'ni oching: **Variables → New Variable**.
6. Quyidagini qo‘shing:

```text
BOT_TOKEN = BotFather bergan token
```

Ixtiyoriy sozlamalar:

```text
MAX_DOWNLOAD_MB = 48
MAX_ITEMS_PER_LINK = 10
DOWNLOAD_TIMEOUT_SECONDS = 600
```

7. **Deploy** yoki **Redeploy** ni bosing.
8. **Deployments → View logs** ichida `YUKLANADI_BOT ishga tushmoqda` yozuvi chiqsa, bot ishlayapti.
9. Telegramda botni ochib `/start` yuboring va public link bilan sinang.

Bu bot polling ishlatadi, shuning uchun alohida domain, port yoki webhook sozlash shart emas. Railway service'ni o‘chirmang: bot doimiy ishlashi uchun service running holatda qolishi kerak.

## 4. Telefon orqali keyingi yangilash

`bot.py` yoki boshqa faylni GitHub'da tahrirlang va commit qiling. Railway GitHub commitni ko‘rib yangi deployni avtomatik boshlaydi. Agar avtomatik deploy o‘chiq bo‘lsa, Railway'da **Deployments → Deploy latest commit** ni bosing.

## Muammolar

**Bot javob bermayapti**

- Railway Variables ichida `BOT_TOKEN` aynan borligini tekshiring.
- Logs ichida `YUKLANADI_BOT ishga tushmoqda` chiqganini tekshiring.
- Telegramda botga `/start` yuboring.

**“Media yuklanmadi” chiqyapti**

- Link private yoki login talab qilmasin.
- Linkni brauzerda inkognito oynada ochib ko‘ring.
- Kichikroq video yoki audio formatini tanlang.
- Platforma extractor'i yangilanishini talab qilayotgan bo‘lishi mumkin; GitHub'da `requirements.txt` dagi `yt-dlp` versiyasini yangilab commit qiling.

**Fayl juda katta**

Audio formatini tanlang yoki manbada pastroq sifatli video yuboring. `MAX_DOWNLOAD_MB` ni oshirish Telegram bot limitiga zid bo‘lishi mumkin, shuning uchun 48 MB atrofida qoldirish tavsiya etiladi.

## Mahalliy test (ixtiyoriy)

Kompyuter shart emas. Agar keyin tekshirmoqchi bo‘lsangiz:

```bash
cp .env.example .env
# .env ichiga BOT_TOKEN yozing
pip install -r requirements.txt
python bot.py
```

FFmpeg audio va video formatlari uchun kerak. Dockerfile uni Railway'da avtomatik o‘rnatadi.

## Foydalanish eslatmasi

Faqat o‘zingiz yuklashga haqqingiz bo‘lgan yoki public va ruxsat etilgan kontentdan foydalaning. Platformalarning shartlari, mualliflik huquqi va shaxsiy hayot qoidalarini buzmaslik foydalanuvchi zimmasida. Ushbu loyiha login cheklovlarini yoki DRM himoyasini aylanib o‘tish uchun mo‘ljallanmagan.