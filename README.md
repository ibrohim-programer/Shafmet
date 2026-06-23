# Shafmet Backend

Django REST Framework asosidagi Shafmet backend loyihasi.

## Ishga tushirish

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Swagger UI:

```text
http://127.0.0.1:8000/
```

## Muhim

`.env`, `.venv`, `db.sqlite3`, `media` va cache fayllar GitHubga qo'shilmaydi. Production uchun `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` va `DJANGO_CSRF_TRUSTED_ORIGINS` qiymatlarini alohida sozlang.

CORS xatosi bo'lmasligi uchun serverga joylaganda `.env` ichida `CORS_ALLOWED_ORIGINS`ga frontend domeningizni to'liq origin ko'rinishida yozing, masalan `https://example.com`. Agar cookie/session bilan ishlatilsa, `CORS_ALLOW_CREDENTIALS=True` qiling.
