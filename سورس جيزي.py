import telebot
import requests
import json
import os
import logging
from datetime import datetime, timedelta
import urllib3

# تعطيل تحذيرات SSL (غير موصى به في بيئات الإنتاج)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# إعدادات البوت
TOKEN = '7640085320:AAFQ13WFPNTW8syD-FzccnYcbF3kboKt68Q'
ADMIN_ID = '6413007479'
GROUP_CHAT_ID = -23  # استبدل هذا بمعرف مجموعتك الفعلي

# إعدادات Djezzy API
DJEZZY_CLIENT_ID = '6E6CwTkp8H1CyQxraPmcEJPQ7xka'
DJEZZY_CLIENT_SECRET = 'MVpXHW_ImuMsxKIwrJpoVVMHjRsa'
DJEZZY_USER_AGENT = 'Djezzy/2.6.7'

# إعدادات تخزين البيانات
DATA_FILE_PATH = 'djezzy_data.json'

# إعدادات الهدية
GIFT_ID = 'TransferInternet2Go'
GIFT_SERVICE_CODE = 'FAMILY4000'
GIFT_SERVICE_ID = 'WALKWIN'

# فترة الانتظار بالساعات
COOLDOWN_HOURS = 24

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# إنشاء كائن البوت
bot = telebot.TeleBot(TOKEN)

# تحميل بيانات المستخدمين
def load_user_data():
    """تحميل بيانات المستخدمين من ملف JSON"""
    if os.path.exists(DATA_FILE_PATH):
        try:
            with open(DATA_FILE_PATH, 'r', encoding='utf-8') as file:
                return json.load(file)
        except json.JSONDecodeError:
            logger.error(f"خطأ في فك ترميز JSON من {DATA_FILE_PATH}")
            return {}
        except Exception as e:
            logger.error(f"خطأ في تحميل بيانات المستخدم: {str(e)}")
            return {}
    return {}

# حفظ بيانات المستخدمين
def save_user_data(data):
    """حفظ بيانات المستخدمين إلى ملف JSON"""
    try:
        # إنشاء المجلد إذا لم يكن موجودًا
        directory = os.path.dirname(DATA_FILE_PATH)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        with open(DATA_FILE_PATH, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4)
        return True
    except Exception as e:
        logger.error(f"خطأ في حفظ بيانات المستخدم: {str(e)}")
        return False

# إخفاء رقم الهاتف
def hide_phone_number(phone_number):
    """إخفاء معظم أرقام الهاتف للخصوصية"""
    if len(phone_number) < 7:
        return phone_number  # قصير جدًا للإخفاء
    return phone_number[:4] + '*******' + phone_number[-2:]

# التحقق من فترة الانتظار
def check_cooldown(last_applied_time):
    """التحقق مما إذا كانت فترة الانتظار قد انتهت"""
    if not last_applied_time:
        return True
    
    try:
        last_time = datetime.fromisoformat(last_applied_time)
        current_time = datetime.now()
        return current_time - last_time >= timedelta(hours=COOLDOWN_HOURS)
    except ValueError:
        logger.error(f"تنسيق وقت غير صالح: {last_applied_time}")
        return True
    except Exception as e:
        logger.error(f"خطأ في التحقق من فترة الانتظار: {str(e)}")
        return True

# تنسيق رسالة فترة الانتظار
def format_cooldown_message(last_applied_time):
    """تنسيق رسالة تحتوي على وقت الانتظار المتبقي"""
    try:
        last_time = datetime.fromisoformat(last_applied_time)
        next_available = last_time + timedelta(hours=COOLDOWN_HOURS)
        remaining = next_available - datetime.now()
        
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        return f"⏳ يرجى الانتظار {hours} ساعة و {minutes} دقيقة قبل طلب هدية جديدة."
    except Exception as e:
        logger.error(f"خطأ في تنسيق رسالة فترة الانتظار: {str(e)}")
        return "⏳ يرجى الانتظار حتى انتهاء فترة الانتظار."

# التحقق من العضوية في المجموعة
def check_membership(chat_id, user_id):
    """التحقق مما إذا كان المستخدم عضوًا في المجموعة المطلوبة"""
    # نسمح لجميع المستخدمين باستخدام البوت بدون شرط العضوية
    return True

# الحصول على بيانات المستخدم
def get_user_data(chat_id):
    """الحصول على بيانات المستخدم لمعرف دردشة محدد"""
    try:
        user_data = load_user_data()
        return user_data.get(str(chat_id), None)
    except Exception as e:
        logger.error(f"خطأ في الحصول على بيانات المستخدم: {str(e)}")
        return None

# تحديث وقت آخر استخدام للهدية
def update_last_applied(chat_id):
    """تحديث طابع الوقت لآخر استخدام للمستخدم"""
    try:
        user_data = load_user_data()
        if str(chat_id) in user_data:
            user_data[str(chat_id)]['last_applied'] = datetime.now().isoformat()
            return save_user_data(user_data)
        return False
    except Exception as e:
        logger.error(f"خطأ في تحديث وقت آخر استخدام: {str(e)}")
        return False

# التحقق من إمكانية تطبيق الهدية
def can_apply_gift(chat_id):
    """التحقق مما إذا كان المستخدم يمكنه التقدم بطلب للحصول على هدية (فحص فترة الانتظار)"""
    try:
        user_data = get_user_data(chat_id)
        if not user_data:
            return True, None
        
        last_applied = user_data.get('last_applied')
        if not check_cooldown(last_applied):
            cooldown_msg = format_cooldown_message(last_applied)
            return False, cooldown_msg
        
        return True, None
    except Exception as e:
        logger.error(f"خطأ في التحقق مما إذا كان المستخدم يمكنه تطبيق الهدية: {str(e)}")
        return False, "⚠️ حدث خطأ أثناء التحقق من الأهلية للهدية."

# إرسال رمز OTP
def send_otp(msisdn):
    """إرسال رمز OTP إلى رقم الهاتف المحدد"""
    url = f"https://apim.djezzy.dz/oauth2/registration"
    payload = f'msisdn={msisdn}&client_id={DJEZZY_CLIENT_ID}&scope=smsotp'
    headers = {
        'User-Agent': DJEZZY_USER_AGENT,
        'Connection': 'close',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cache-Control': 'no-cache'
    }
    
    try:
        response = requests.post(
            url, 
            data=payload, 
            headers=headers, 
            verify=False,
            timeout=30
        )
        logger.info(f"استجابة إرسال OTP: {response.status_code}")
        logger.debug(f"محتوى استجابة إرسال OTP: {response.text}")
        
        return response.status_code == 200
    except requests.RequestException as error:
        logger.error(f"خطأ في إرسال OTP: {error}")
        return False

# التحقق من رمز OTP
def verify_otp(msisdn, otp):
    """التحقق من OTP والحصول على رموز الوصول"""
    url = f"https://apim.djezzy.dz/oauth2/token"
    payload = (
        f'otp={otp}&mobileNumber={msisdn}&scope=openid'
        f'&client_id={DJEZZY_CLIENT_ID}'
        f'&client_secret={DJEZZY_CLIENT_SECRET}'
        f'&grant_type=mobile'
    )
    headers = {
        'User-Agent': DJEZZY_USER_AGENT,
        'Connection': 'close',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cache-Control': 'no-cache'
    }
    
    try:
        response = requests.post(
            url, 
            data=payload, 
            headers=headers, 
            verify=False,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        
        logger.error(f"فشل التحقق من OTP: {response.status_code}, {response.text}")
        return None
    except requests.RequestException as error:
        logger.error(f"خطأ في التحقق من OTP: {error}")
        return None

# تطبيق هدية الإنترنت
def apply_gift(msisdn, access_token):
    """تطبيق هدية الإنترنت على حساب المستخدم"""
    url = f"https://apim.djezzy.dz/djezzy-api/api/v1/subscribers/{msisdn}/subscription-product?include="
    
    payload = {
        "data": {
            "id": GIFT_ID,
            "type": "products",
            "meta": {
                "services": {
                    "steps": 10000,
                    "code": GIFT_SERVICE_CODE,
                    "id": GIFT_SERVICE_ID
                }
            }
        }
    }
    
    headers = {
        'User-Agent': DJEZZY_USER_AGENT,
        'Connection': 'Keep-Alive',
        'Content-Type': 'application/json; charset=utf-8',
        'Host': 'apim.djezzy.dz',
        'Authorization': f'Bearer {access_token}'
    }
    
    try:
        response = requests.post(
            url, 
            json=payload, 
            headers=headers, 
            verify=False,
            timeout=30
        )
        
        logger.info(f"استجابة تطبيق الهدية: {response.status_code}")
        logger.debug(f"محتوى استجابة تطبيق الهدية: {response.text}")
        
        response_data = response.json()
        
        if "successfully done" in response_data.get('message', ''):
            return True, None
        else:
            error_message = response_data.get('message', 'خطأ غير معروف')
            return False, error_message
            
    except requests.RequestException as error:
        logger.error(f"خطأ في تطبيق الهدية: {error}")
        return False, "حدث خطأ أثناء تطبيق الهدية"

# تخزين بيانات المستخدم
def store_user_data(chat_id, user_info):
    """تخزين بيانات مصادقة المستخدم"""
    try:
        user_data = load_user_data()
        user_data[str(chat_id)] = user_info
        return save_user_data(user_data)
    except Exception as e:
        logger.error(f"خطأ في تخزين بيانات المستخدم: {str(e)}")
        return False

# أمر البداية
@bot.message_handler(commands=['start'])
def handle_start(message):
    """معالجة أمر /start"""
    chat_id = message.chat.id
    
    # عرض زر إرسال الرقم مباشرة بدون التحقق من العضوية
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton(
        text='📱 إرسال رقم الهاتف 📱', 
        callback_data='send_number'
    ))
    
    # إضافة أزرار القنوات للترويج فقط
    markup.add(telebot.types.InlineKeyboardButton(
        text='قناة المطور 📢', 
        url='https://t.me/vi_10005'
    ))
    markup.add(telebot.types.InlineKeyboardButton(
        text='قناة الموطور 📢', 
        url='https://t.me/vi_10005'
    ))
    
    bot.send_message(
        chat_id,
        '👋 مرحبًا! الرجاء إرسال رقم هاتف Djezzy الذي يبدأ بـ 07',
        reply_markup=markup
    )

# معالجة رد الاستدعاء لإرسال الرقم
@bot.callback_query_handler(func=lambda call: call.data == 'send_number')
def handle_send_number(callback_query):
    """معالجة رد الاستدعاء send_number"""
    chat_id = callback_query.message.chat.id
    bot.send_message(chat_id, '📱 أرسل رقم هاتفك Djezzy الذي يبدأ بـ 07:')
    bot.register_next_step_handler_by_chat_id(chat_id, handle_phone_number)

# معالجة إدخال رقم الهاتف
def handle_phone_number(message):
    """معالجة إدخال رقم الهاتف"""
    chat_id = message.chat.id
    text = message.text
    
    if not text:
        bot.send_message(chat_id, '⚠️ الرجاء إدخال رقم هاتف صالح.')
        return
        
    if text.startswith('07') and len(text) == 10 and text.isdigit():
        msisdn = '213' + text[1:]
        if send_otp(msisdn):
            bot.send_message(chat_id, '🔢 تم إرسال رمز OTP. أدخله الآن:')
            # تخزين رقم الهاتف مؤقتًا للخطوة التالية
            bot.register_next_step_handler_by_chat_id(
                chat_id, 
                lambda msg: handle_otp(msg, msisdn)
            )
        else:
            bot.send_message(
                chat_id, 
                '⚠️ فشل إرسال رمز OTP. تحقق من الرقم وحاول مرة أخرى.'
            )
    else:
        bot.send_message(
            chat_id, 
            '⚠️ أدخل رقمًا صالحًا يبدأ بـ 07 ويتكون من 10 أرقام.'
        )

# معالجة إدخال رمز OTP
def handle_otp(message, msisdn):
    """معالجة التحقق من OTP"""
    chat_id = message.chat.id
    otp = message.text
    
    if not otp or not otp.isdigit():
        bot.send_message(chat_id, '⚠️ الرجاء إدخال رمز OTP صالح (أرقام فقط).')
        return
        
    tokens = verify_otp(msisdn, otp)
    
    if tokens:
        # تخزين بيانات المستخدم
        user_info = {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'telegram_id': chat_id,
            'msisdn': msisdn,
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'last_applied': None
        }
        
        if store_user_data(chat_id, user_info):
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton(
                text='تفعل هديه يومياً 🎁', 
                callback_data='walkwingift'
            ))
            
            bot.send_message(
                chat_id, 
                '🎉 تم التحقق بنجاح! اختر الإجراء المطلوب:',
                reply_markup=markup
            )
        else:
            bot.send_message(
                chat_id, 
                '⚠️ حدث خطأ أثناء حفظ البيانات. الرجاء المحاولة مرة أخرى.'
            )
    else:
        bot.send_message(chat_id, '⚠️ رمز OTP غير صحيح. الرجاء المحاولة مرة أخرى.')

# معالجة رد الاستدعاء لتطبيق الهدية
@bot.callback_query_handler(func=lambda call: call.data == 'walkwingift')
def handle_walkwingift(callback_query):
    """معالجة تطبيق هدية الإنترنت"""
    chat_id = callback_query.message.chat.id
    user = get_user_data(chat_id)
    
    if not user:
        bot.send_message(
            chat_id, 
            '⚠️ لم يتم العثور على بيانات المستخدم. الرجاء إعادة التسجيل باستخدام /start'
        )
        return
    
    # التحقق من فترة الانتظار
    can_apply, cooldown_message = can_apply_gift(chat_id)
    if not can_apply:
        bot.send_message(chat_id, cooldown_message)
        return
    
    # تطبيق الهدية
    success, error_message = apply_gift(
        user['msisdn'], 
        user['access_token']
    )
    
    if success:
        hidden_phone = hide_phone_number(user['msisdn'])
        update_last_applied(chat_id)
        
        success_message = (
            f"🎉 تم تفعيل الأنترنت بنجاح!\n\n"
            f"👤 الاسم: {user.get('first_name', 'غير معروف')}\n"
            f"🧑‍💻 المستخدم: @{user.get('username', 'غير معروف')}\n"
            f"📞 الرقم: {hidden_phone}"
        )
        
        bot.send_message(chat_id, success_message)
    else:
        error_msg = f"⚠️ خطأ: {error_message}"
        bot.send_message(chat_id, error_msg)

# أمر المساعدة
@bot.message_handler(commands=['help'])
def handle_help(message):
    """معالجة أمر /help"""
    help_text = (
        "🌟 *مرحبًا بك في بوت هدايا Djezzy* 🌟\n\n"
        "هذا البوت يساعدك في الحصول على هدايا الإنترنت من Djezzy.\n\n"
        "الأوامر المتاحة:\n"
        "/start - بدء استخدام البوت\n"
        "/help - عرض هذه المساعدة\n\n"
        "للحصول على هدية، اتبع الخطوات التالية:\n"
        "1. أدخل رقم هاتفك Djezzy\n"
        "2. أدخل رمز OTP الذي ستستلمه على هاتفك\n"
        "3. اضغط على زر 'AIZEN ' للحصول على الهدية\n\n"
        "ملاحظة: يمكنك الحصول على هدية واحدة كل 24 ساعة."
    )
    
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

# معالج الرسائل غير المعروفة
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.send_message(
        message.chat.id, 
        "⚠️ أمر غير معروف. استخدم /start للبدء أو /help للمساعدة."
    )

# بداية تشغيل البوت
if __name__ == "__main__":
    try:
        logger.info("جاري بدء تشغيل بوت هدايا Djezzy...")
        # بدء استطلاع البوت
        bot.polling(none_stop=True, interval=1)
        logger.info("البوت يعمل. اضغط Ctrl+C للخروج.")
    except KeyboardInterrupt:
        logger.info("تم إيقاف البوت بواسطة المستخدم")
    except Exception as e:
        logger.error(f"خطأ أثناء تشغيل البوت: {str(e)}", exc_info=True)

