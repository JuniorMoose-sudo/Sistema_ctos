from django.contrib import admin
from django.utils.html import format_html

from .models import CTO, Ocorrencia


@admin.register(CTO)
class CTOAdmin(admin.ModelAdmin):
    list_display = ("nome", "bairro", "status_atual", "portas_livres_atual", "capacidade", "ativa")
    list_filter = ("bairro", "status_atual", "ativa")
    search_fields = ("nome", "bairro")


@admin.register(Ocorrencia)
class OcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("cto", "tecnico", "situacao", "motivo", "portas_livres", "foto_thumb", "criado_em")
    list_select_related = ("cto", "tecnico")
    list_filter = ("situacao", "motivo", "criado_em")
    search_fields = ("cto__nome", "tecnico__username")
    readonly_fields = [f.name for f in Ocorrencia._meta.fields]  # append-only: não editar pelo admin

    @admin.display(description="Foto")
    def foto_thumb(self, obj):
        if obj.foto:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="height:60px;border-radius:4px;"/></a>',
                obj.foto.url,
                obj.foto.url,
            )
        return "—"

    def has_change_permission(self, request, obj=None):
        return False  # reforça a regra de append-only também no admin
