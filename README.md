# Kochmon API

## Локально
    python -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    python -m scripts.create_admin admin@example.com 'StrongPassword'
    python -m scripts.migrate_listing_fields
    python -m scripts.seed_catalog
    uvicorn app.main:app --reload --port 8000
    # docs: http://localhost:8000/docs
    python -m pytest -q

## AWS (Docker + nginx)
    cp .env.example .env   # заполнить DB_PASSWORD, SECRET_KEY, CORS_ORIGINS и ключи подключаемых сервисов
    docker compose up -d --build
    docker compose exec api python -m scripts.migrate_listing_fields
    docker compose exec api python -m scripts.seed_catalog
    docker compose exec api python -m scripts.create_admin admin@kochmon.com.kg 'StrongPassword'
    curl http://localhost/api/health

Security group: открыты 80 и 443, порт 5432 закрыт.
Сертификат: certbot certonly --webroot -w ./certbot/www -d api.kochmon.com.kg, затем HTTPS-блок в nginx.conf.
AUTO_CREATE_TABLES=true временно заменяет миграции; для изменений схемы нужен Alembic.

## Интеграции
- Google OAuth: зарегистрируйте callback `GOOGLE_REDIRECT_URI` в Google Cloud Console.
- Интернет-поиск: включите Custom Search JSON API и заполните `GOOGLE_CSE_API_KEY` и `GOOGLE_CSE_CX`.
- AI: заполните `GEMINI_API_KEY`.
- Сброс пароля: настройте `SMTP_*`; ссылка ведёт на `FRONTEND_URL`.
- Telegram: заполните `TELEGRAM_BOT_*`, задайте случайный `TELEGRAM_WEBHOOK_SECRET`, затем вызовите
  `POST /api/channels/telegram/setup` с токеном администратора.
- WhatsApp: заполните `WHATSAPP_*` и создайте в Meta одобренный шаблон с параметром кода,
  совпадающий с `WHATSAPP_TEMPLATE_NAME` и `WHATSAPP_TEMPLATE_LANGUAGE`.
- Рекламные заявки сохраняются в backend и требуют одобрения администратора через
  `POST /api/advertising/campaigns/{id}/approve`.
- Картинки хранятся в Docker volume `uploads`; для отдельного домена API задайте `API_PUBLIC_URL`.

Без внешних ключей соответствующие маршруты отвечают явной ошибкой `503`, а не тестовыми успешными данными.
