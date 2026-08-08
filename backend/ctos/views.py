from django.shortcuts import render


def tecnico_login_view(request):
    return render(request, "tecnico/login.html")


def tecnico_app_view(request):
    return render(request, "tecnico/app.html")
