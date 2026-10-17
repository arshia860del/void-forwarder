# راهنمای استقرار در سرورلس TGCloud (TGCloud Serverless Deployment Guide)

این راهنما نحوه استقرار پروژه **سیستم فوروارد و اعلان پیام‌های پشتیبانی تلگرام** در سرویس‌های ابری بدون سرور (Serverless) به‌ویژه **TGCloud** را توضیح می‌دهد.

---

## ۱. درک نحوه عملکرد سرورلس برای حساب‌های کاربری تلگرام (MTProto vs Webhook)

- **بات‌های معمولی تلگرام (Bot API)** بر پایه وب‌هوک (Webhook) کار می‌کنند.
- **اکانت‌های واقعی تلگرام (User Accounts)** مثل حساب پشتیبانی شما، از پروتکل باینری **MTProto** استفاده می‌کنند که نیازمند اتصال پایدار TCP است.
- **راهکار مهندسی ما:** استفاده از **`Telethon StringSession`**!
  تمام کلیدهای احراز هویت در متغیر محیطی (`TELEGRAM_STRING_SESSION`) قرار می‌گیرد و سیستم ۱۰۰٪ بدون نیاز به فایل محلی کار می‌کند.

---

## ۲. مراحل راه‌اندازی گام به گام در TGCloud

### مرحله ۱: دریافت شناسه API تلگرام
1. وارد سایت [my.telegram.org](https://my.telegram.org) شوید.
2. در بخش **API development tools** یک اپ بسازید.
3. مقادیر **`api_id`** و **`api_hash`** را کپی کنید.

### مرحله ۲: ساخت ربات اعلان و دریافت آیدی عددی
1. در تلگرام وارد [@BotFather](https://t.me/BotFather) شده و دستور `/newbot` را بزنید.
2. توکن ربات را کپی کنید.
3. **مهم:** وارد ربات شده و دکمه **Start** (`/start`) را بزنید.
4. آیدی عددی اکانت خود را از [@userinfobot](https://t.me/userinfobot) بگیرید.

### مرحله ۳: ساخت رشته نشست یک‌بار مصرف (`StringSession`)
روی کامپیوتر خود اجرا کنید:
```bash
pip install -r requirements.txt
python generate_session.py
```
شماره و کد ارسالی را بزنید و رشته `TELEGRAM_STRING_SESSION` را کپی کنید.

### مرحله ۴: اضافه کردن متغیرها در TGCloud
در داشبورد TGCloud در بخش Environment Variables مقادیر زیر را ثبت کنید:
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_STRING_SESSION`
- `NOTIFICATION_BOT_TOKEN`
- `MAIN_ACCOUNT_ID`
- `TIMEZONE` (مثلا Asia/Tehran)
