from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
# E-mails aparecem no terminal: testa sem gastar cota do Gmail
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"