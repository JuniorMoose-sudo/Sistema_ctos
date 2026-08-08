import random
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from ctos.models import CTO, Ocorrencia, Situacao, Motivo

User = get_user_model()

class Command(BaseCommand):
    help = "Gera ocorrências de teste para popular o dashboard localmente."

    def handle(self, *args, **options):
        tecnicos = list(User.objects.filter(is_staff=False))
        if not tecnicos:
            tecnicos = list(User.objects.all())
        
        ctos = list(CTO.objects.all()[:50])
        if not ctos:
            self.stdout.write(self.style.ERROR("Nenhuma CTO encontrada. Execute importar_kmz primeiro."))
            return

        situacoes = [Situacao.NORMAL, Situacao.PROXIMA_LOTACAO, Situacao.LOTADA, Situacao.DANIFICADA]
        motivos = [Motivo.SEM_PORTA_LIVRE, Motivo.SEM_SPLITTER, Motivo.FIBRA_ROMPIDA, Motivo.CAIXA_QUEBRADA]

        criadas = 0
        for _ in range(30):
            cto = random.choice(ctos)
            tecnico = random.choice(tecnicos) if tecnicos else User.objects.first()
            situacao = random.choices(situacoes, weights=[40, 20, 30, 10])[0]
            motivo = random.choice(motivos) if situacao != Situacao.NORMAL else None
            
            portas_usadas = random.randint(10, 16) if situacao in [Situacao.LOTADA, Situacao.PROXIMA_LOTACAO] else random.randint(0, 8)
            portas_livres = 16 - portas_usadas

            Ocorrencia.objects.create(
                cto=cto,
                tecnico=tecnico,
                situacao=situacao,
                motivo=motivo,
                portas_usadas=portas_usadas,
                portas_livres=portas_livres,
                latitude_registro=cto.latitude,
                longitude_registro=cto.longitude,
                observacao="Ocorrência de teste gerada automaticamente para desenvolvimento local."
            )
            criadas += 1

        self.stdout.write(self.style.SUCCESS(f"{criadas} ocorrências de teste geradas com sucesso!"))
