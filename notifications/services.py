import logging
from django.conf import settings
from .models import FCMDevice

logger = logging.getLogger(__name__)

# Firebase admin may not be initialized if credentials are not provided.
# We try to import it, but won't crash if it is not configured.
firebase_app_initialized = False
try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    
    # Try to initialize firebase-admin using default credentials or custom JSON
    # Typically initialized in django's ready() or config/wsgi.py.
    # We check if it is already initialized.
    if not firebase_admin._apps:
        # Check if credential file exists
        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", None)
        if cred_path:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            firebase_app_initialized = True
        else:
            # Fallback to default
            try:
                firebase_admin.initialize_app()
                firebase_app_initialized = True
            except Exception:
                pass
    else:
        firebase_app_initialized = True
except ImportError:
    logger.warning("firebase-admin package is not installed.")

def send_push_notification(user, title, body, data=None):
    """
    Foydalanuvchining barcha faol qurilmalariga push bildirishnoma yuborish.
    """
    devices = FCMDevice.objects.filter(user=user)
    if not devices.exists():
        logger.info(f"User {user.phone} uchun ro'yxatdan o'tgan FCM qurilmalar topilmadi.")
        return 0

    tokens = [d.device_token for d in devices]
    logger.info(f"FCM: '{title}' xabari {user.full_name} ({len(tokens)} ta qurilma) uchun yuborilmoqda.")
    
    if not firebase_app_initialized:
        # Fallback logging if Firebase is not configured / initialized
        logger.warning(
            f"[MOCK FCM] Firebase sozlanmagan. Xabar yuborilmadi. "
            f"Foydalanuvchi: {user.full_name}, Sarlavha: {title}, Xabar: {body}, Data: {data}"
        )
        return 0

    success_count = 0
    for device in devices:
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=device.device_token,
            )
            messaging.send(message)
            success_count += 1
        except Exception as e:
            logger.error(f"FCM device token {device.device_token} ga yuborishda xatolik: {e}")
            # Agar token eskirgan/yaroqsiz bo'lsa, uni o'chirib tashlaymiz
            if "registration-token-not-registered" in str(e).lower() or "invalid-registration-token" in str(e).lower():
                logger.info(f"Yaroqsiz token o'chirilmoqda: {device.device_token}")
                device.delete()

    return success_count
