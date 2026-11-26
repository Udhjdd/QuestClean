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

def take_screenshot(page, chat_id, filename="error_screen.png"):
    try:
        page.screenshot(path=filename)
        with open(filename, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption="📸 لقطة للشاشة عند حدوث الخطأ")
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
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Linux; Android 13; Pixel 9 Pro XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                viewport={"width": 412, "height": 915},
                is_mobile=True, has_touch=True
            )
            page = context.new_page()
            
            # 1. فتح صفحة الدخول
            page.goto("https://accounts.google.com/signin", timeout=60000)
            time.sleep(5)
            
            # 2. كتابة الإيميل
            try:
                page.locator('input[name="identifier"]').wait_for(state="visible", timeout=15000)
                page.locator('input[name="identifier"]').fill(email)
                page.keyboard.press("Enter")
                time.sleep(5)
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ لم أجد خانة الإيميل: {e}")
                take_screenshot(page, chat_id)
                browser.close()
                return
            
            # 3. التعامل مع شاشة اختيار الحساب (إذا ظهرت)
            if "Choose an account" in page.content():
                bot.send_message(chat_id, "👤 ظهرت شاشة اختيار الحساب...")
                try:
                    page.locator(f'text="{email}"').first.click()
                    time.sleep(5)
                except: pass

            # 4. كتابة كلمة المرور (مع محاولات متعددة)
            try:
                # قد تكون الصفحة مختلفة، نجرب عدة محددات
                pass_input = page.locator('input[type="password"], input[name="Passwd"]').first
                pass_input.wait_for(state="visible", timeout=20000)
                pass_input.fill(password)
                page.keyboard.press("Enter")
                time.sleep(10)
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ لم أجد خانة كلمة المرور. قد تكون هناك شاشة تحقق أولية. سأرسل لك صورة.")
                take_screenshot(page, chat_id)
                browser.close()
                return
            
            # 5. التحقق بخطوتين
            content = page.content()
            if "2-Step Verification" in content or "Tap Yes" in content or "Choose how you want to sign in" in content:
                bot.send_message(chat_id, "🔑 جوجل تطلب تحقق! افتح هاتفك واضغط على إشعار جوجل. (انتظر 45 ثانية)...")
                # نحاول الضغط على Tap Yes إذا كان موجوداً
                try:
                    tap_yes = page.locator(':text-matches("Tap Yes|phone or tablet")').first
                    if tap_yes.is_visible():
                        tap_yes.click()
                        bot.send_message(chat_id, "✅ تم الضغط على خيار Tap Yes. افتح هاتفك الآن.")
                except: pass
                time.sleep(45)
                
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
            
            # الضغط على Continue إذا ظهر
            try:
                page.locator('button:has-text("Continue"), button:has-text("Allow")').first.click()
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
                take_screenshot(page, chat_id)
                
            browser.close()
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ عام: {str(e)[:300]}")

print("البوت يعمل... أرسل /start في تيليجرام.")
bot.polling(none_stop=True)
