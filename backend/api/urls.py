from django.urls import path

from . import views

urlpatterns = [
    path("auth/token/", views.ObterTokenView.as_view()),  # login do técnico -> retorna token
    path("ctos/", views.CTOListView.as_view()),  # visão consolidada (mapa do gestor)
    path("ctos/proximas/", views.CTOsProximasView.as_view()),
    path("ctos/buscar/", views.CTOsBuscarView.as_view()),
    path("ctos/<int:pk>/", views.CTODetalheView.as_view()),
    path("ocorrencias/", views.OcorrenciaListCreateView.as_view()),
]
