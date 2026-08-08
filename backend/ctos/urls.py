from django.urls import path
from . import views

urlpatterns = [
    path("", views.tecnico_app_view, name="tecnico_app"),
    path("login/", views.tecnico_login_view, name="tecnico_login"),
]
