from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("dashboard/", views.agent_dashboard, name="dashboard"),
    path("faqs/", views.faqs, name="faqs"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("notifications/", views.notification_settings, name="notification_settings"),
    path("api/chat/", views.chat_api, name="chat_api"),
]
