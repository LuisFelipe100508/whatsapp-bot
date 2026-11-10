from django.urls import path

from .views import SendRemindersView

urlpatterns = [
    path("send-reminders/", SendRemindersView.as_view(), name="send-reminders"),
]