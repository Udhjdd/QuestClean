import telebot
import threading
import time
import http.server
import socketserver
import urllib.parse
import requests
import os
from playwright.sync_api import sync_playwright

# --- إعدادات بوت التيليجرام ---
TELEGRAM_TOKEN = "9032675094:AAGk8zSeWv9ewfztsAATj6_8utGZedynV44"
CHAT_ID = "7306346652"

# --- إعدادات جوجل ---
CLIENT_ID = "469058699729-6bh3d12qsj1775uni0tj7gtu7uld61iv.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "http://localhost:8080"
SCOPE = "https://www.googleapis.com/auth/games"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
auth_code = None
user_credentials = {}

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        if "/?code=" in self.path:
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if 'code' in params:
                auth_code = params['code'][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Success! You can close this window.")

def start_server():
    with socketserver.TCPServer(("", 8080), Handler) as httpd:
        httpd.handle_request()

def take_screenshot(page, chat_id, step_name):
    try:
        filename = f"step_{step_name}.png"
        page.screenshot(path=filename)
        with open(filename, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption=f"📸 الخطوة: {step_name}")
    except Exception as e:
        print(f"Screenshot failed: {e}")

@bot.message_handler(commands=['start'])
def start_bot(message):
    bot.reply_to(message, "أهلاً بك سيدي! 🧛‍♂️\nالرجاء إرسال إيميل جوجل الخاص بك (كامل):")
    bot.register_next_step_handler(message, get_email)

def get_email(message):
    chat_id = message.chat.id
    user_credentials[chat_id] = {"email": message.text.strip()}
    bot.reply_to(message, "تم استلام الإيميل. الآن أرسل كلمة المرور:")
    bot.register_next_step_handler(message, get_password)

def get_password(message):
    chat_id = message.chat.id
    user_credentials[chat_id]["password"] = message.text.strip()
    bot.reply_to(message, "تم استلام البيانات. جاري تشغيل المتصفح...")
    threading.Thread(target=login_and_get_token, args=(chat_id,)).start()

def login_and_get_token(chat_id):
    global auth_code
    email = user_credentials[chat_id]["email"]
    password = user_credentials[chat_id]["password"]
    
    bot.send_message(chat_id, "🚀 جاري فتح المتصفح وتسجيل الدخول...")
    
    try:
        with sync_playwright() as p:
            # التعديل 1: إضافة أوامر تمويه لتجاوز الحظر
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", 
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 9 Pro XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                viewport={"width": 412, "height": 915},
                is_mobile=True, 
                has_touch=True
            )
            # حقن كود إخفاء البوت
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page = context.new_page()
            
            # 1. فتح صفحة الدخول
            page.goto("https://accounts.google.com/signin", timeout=60000)
            time.sleep(5)
            take_screenshot(page, chat_id, "1_صفحة_الدخول")
            
            # 2. كتابة الإيميل (محاكاة الكتابة البشرية)
            try:
                page.locator('input[name="identifier"]').wait_for(state="visible", timeout=15000)
                # التعديل 2: استخدام press_sequentially بدلاً من fill
                page.locator('input[name="identifier"]').press_sequentially(email, delay=100)
                time.sleep(1)
                take_screenshot(page, chat_id, "2_بعد_كتابة_الإيميل")
                
                page.keyboard.press("Enter")
                time.sleep(5)
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ لم أجد خانة الإيميل: {e}")
                take_screenshot(page, chat_id, "error_email")
                browser.close()
                return
            
            # 3. التعامل مع شاشة اختيار الحساب (إذا ظهرت)
            if "Choose an account" in page.content():
                bot.send_message(chat_id, "👤 ظهرت شاشة اختيار الحساب...")
                try:
                    page.locator(f'text="{email}"').first.click()
                    time.sleep(5)
                    take_screenshot(page, chat_id, "3_اختيار_الحساب")
                except: pass

            # 4. كتابة كلمة المرور
            try:
                pass_input = page.locator('input[type="password"], input[name="Passwd"]').first
                pass_input.wait_for(state="visible", timeout=20000)
                # التعديل 3: محاكاة الكتابة البشرية للباسورد
                pass_input.press_sequentially(password, delay=100)
                time.sleep(1)
                take_screenshot(page, chat_id, "4_بعد_كتابة_الباسورد")
                
                page.keyboard.press("Enter")
                time.sleep(10)
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ لم أجد خانة كلمة المرور.")
                take_screenshot(page, chat_id, "error_password")
                browser.close()
                return
            
            # 5. التحقق بخطوتين
            content = page.content()
            if "2-Step Verification" in content or "Tap Yes" in content or "Choose how you want to sign in" in content:
                bot.send_message(chat_id, "🔑 جوجل تطلب تحقق! افتح هاتفك واضغط على إشعار جوجل. (انتظر 45 ثانية)...")
                take_screenshot(page, chat_id, "5_شاشة_التحقق")
                try:
                    tap_yes = page.locator(':text-matches("Tap Yes|phone or tablet")').first
                    if tap_yes.is_visible():
                        tap_yes.click()
                        bot.send_message(chat_id, "✅ تم الضغط على خيار Tap Yes. افتح هاتفك الآن.")
                except: pass
                time.sleep(45)
                take_screenshot(page, chat_id, "6_بعد_التحقق")
                
            bot.send_message(chat_id, "✅ تم تجاوز الحماية. جاري طلب الصلاحيات...")
            
            # 6. طلب الصلاحيات
            auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "scope": SCOPE,
                "access_type": "offline",
                "prompt": "consent"
            })
            
            threading.Thread(target=start_server).start()
            time.sleep(2)
            
            page.goto(auth_url, timeout=60000)
            time.sleep(3)
            take_screenshot(page, chat_id, "7_صفحة_الصلاحيات")
            
            # الضغط على Continue إذا ظهر
            try:
                page.locator('button:has-text("Continue"), button:has-text("Allow")').first.click()
                time.sleep(2)
                take_screenshot(page, chat_id, "8_بعد_الموافقة")
            except: pass
                
            bot.send_message(chat_id, "⏳ في انتظار التقاط الكود من جوجل...")
            
            for _ in range(30):
                if auth_code: break
                time.sleep(1)
                
            if auth_code:
                bot.send_message(chat_id, "🎉 تم التقاط الكود بنجاح!\nجاري تحويله إلى توكن...")
                
                token_url = "https://oauth2.googleapis.com/token"
                res = requests.post(token_url, data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "code": auth_code,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code"
                })
                token_data = res.json()
                
                if 'refresh_token' in token_data:
                    rt = token_data['refresh_token']
                    bot.send_message(chat_id, f"✅ **نجاح ساحق!**\nهذا هو الـ Refresh Token:\n`{rt}`\n\nانسخه.")
                else:
                    bot.send_message(chat_id, f"⚠️ لم أجد refresh_token. الرد: {token_data}")
            else:
                bot.send_message(chat_id, "❌ فشل التقاط الكود (انتهت المهلة).")
                take_screenshot(page, chat_id, "error_auth_code")
                
            browser.close()
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ عام: {str(e)[:300]}")

print("البوت يعمل... أرسل /start في تيليجرام.")
bot.polling(none_stop=True)
