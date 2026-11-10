from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
# E-mails aparecem no terminal: testa sem gastar cota do Gmail
# Padrão: e-mails aparecem no terminal. Para testar o Gmail real, defina EMAIL_BACKEND no .env.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")