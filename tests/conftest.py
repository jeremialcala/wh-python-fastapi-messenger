# -*- coding: utf-8 -*-
"""
    Settings are read at import time all over the project, so they are pinned here before anything else is imported.
    Environment variables win over config.env: the tests never see real credentials nor reach a real service.
"""
import os

os.environ.update({
    "ADMIN_API_KEY": "test-admin-api-key-0123456789abcdef",
    "FACEBOOK_APP_SECRET": "test-app-secret",

    "CLIENT_ID": "test",
    "NATIONAL_ID_URL": "http://127.0.0.1:1",

    "DB_NAME": "test",
    # Nothing listens on port 1: a test that forgets to mock the database fails fast instead of writing somewhere.
    "DB_HOST": "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=500",
    "DB_USERNAME": "test",
    "DB_PASSWORD": "test",

    "SENDER_EMAIL": "test@example.com",
    "SENDER_PASSWORD": "test",
    "GMAIL_SERVER_URL": "127.0.0.1",
    "GMAIL_SERVER_PORT": "1",

    "EXPIRATION_TIME": "60",
    "ACTIVATION_CODE_LENGTH": "6",
    "PASSWORD_LENGTH": "12",

    "QMS_SERVER": "127.0.0.1",
    "QMS_USER": "test",
    "QMS_PASSWORD": "test",

    "KEY_SIZE": "2048",
    "PRIVATE_KEY_FILENAME": "certs/{UUID}_private.pem",
    "PUBLIC_KEY_FILENAME": "certs/{UUID}_public.pem",

    "ENVIRONMENT": "development",
    "VERSION": "0.0.0",

    "VERIFY_TOKEN": "test",

    "FACEBOOK_GRAPH_URL": "http://127.0.0.1:1/{fb_id}?access_token={ACCESSTOKEN}",
    "FACEBOOK_WHATSAPP_MESSAGE": "http://127.0.0.1:1/{version}/{PhoneNumberId}/messages",
    "FACEBOOK_GRAPH_VERSION": "v19.0",
})
