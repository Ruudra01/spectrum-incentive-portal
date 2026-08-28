from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("dashboard/", views.agent_dashboard, name="dashboard"),
    path("log-work/", views.log_work, name="log_work"),
    path("faqs/", views.faqs, name="faqs"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("notifications/", views.notification_settings, name="notification_settings"),

    path("manager/", views.manager_team, name="manager_team"),
    path("manager/programs/", views.manager_programs, name="manager_programs"),
    path("manager/approvals/", views.manager_approvals, name="manager_approvals"),

    path("director/", views.director_overview, name="director_overview"),
    path("director/programs/", views.director_programs, name="director_programs"),
    path("director/approvals/", views.director_approvals, name="director_approvals"),

    path("api/chat/", views.chat_api, name="chat_api"),
    path("dev/reset-store/", views.dev_reset_store, name="dev_reset_store"),
]
