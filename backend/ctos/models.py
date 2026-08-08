from django.conf import settings
from django.db import models


class Situacao(models.TextChoices):
    NORMAL = "normal", "Normal"
    PROXIMA_LOTACAO = "proxima_lotacao", "Próxima da lotação"
    LOTADA = "lotada", "Lotada"
    DANIFICADA = "danificada", "Danificada"


class Motivo(models.TextChoices):
    SEM_PORTA_LIVRE = "sem_porta_livre", "Sem porta livre"
    SEM_SPLITTER = "sem_splitter", "Sem splitter"
    PORTA_ROMPIDA = "porta_rompida", "Porta rompida"
    FIBRA_ROMPIDA = "fibra_rompida", "Fibra rompida"
    CAIXA_QUEBRADA = "caixa_quebrada", "Caixa quebrada"
    POSTE_INTERDITADO = "poste_interditado", "Poste interditado"
    SEM_ENERGIA = "sem_energia", "Sem energia"
    CTO_INEXISTENTE = "cto_inexistente", "CTO inexistente"
    CTO_MUITO_DISTANTE = "cto_muito_distante", "CTO muito distante"
    OUTRO = "outro", "Outro"


class CTO(models.Model):
    """
    Cadastro fixo da CTO. Vem da importação do KMZ (Fase 0) + geocodificação
    Nominatim para o bairro. Capacidade/splitter iniciam nulos e são
    preenchidos organicamente pelas equipes em campo -- não são pré-cadastro.

    status_atual NUNCA é editado diretamente. Ele é sempre recalculado a
    partir da última Ocorrencia (ver Ocorrencia.save()).
    """

    nome = models.CharField(max_length=255, unique=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    bairro = models.CharField(max_length=100, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)

    # Preenchidos organicamente pelas equipes de campo, começam vazios.
    capacidade = models.PositiveIntegerField(null=True, blank=True)
    splitter = models.CharField(max_length=20, null=True, blank=True)

    status_atual = models.CharField(
        max_length=20, choices=Situacao.choices, default=Situacao.NORMAL
    )
    portas_livres_atual = models.IntegerField(null=True, blank=True)

    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "CTO"
        verbose_name_plural = "CTOs"
        indexes = [
            models.Index(fields=["bairro"]),
            models.Index(fields=["status_atual"]),
        ]

    def __str__(self):
        return self.nome


class Ocorrencia(models.Model):
    """
    Log append-only. Nunca é editado nem apagado -- é a fonte de verdade do
    histórico ("quantas vezes lotou", "tempo médio até expansão", etc.).
    """

    cto = models.ForeignKey(CTO, on_delete=models.PROTECT, related_name="ocorrencias")
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    situacao = models.CharField(max_length=20, choices=Situacao.choices)
    motivo = models.CharField(
        max_length=30, choices=Motivo.choices, null=True, blank=True
    )

    portas_usadas = models.IntegerField(null=True, blank=True)
    portas_livres = models.IntegerField(null=True, blank=True)

    foto = models.ImageField(upload_to="ocorrencias/%Y/%m/", null=True, blank=True)
    observacao = models.TextField(null=True, blank=True)

    # GPS do técnico no momento do envio -- pode divergir da CTO cadastrada.
    latitude_registro = models.DecimalField(max_digits=10, decimal_places=7)
    longitude_registro = models.DecimalField(max_digits=10, decimal_places=7)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ocorrência"
        verbose_name_plural = "Ocorrências"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["cto", "-criado_em"]),
            models.Index(fields=["situacao"]),
            models.Index(fields=["criado_em"]),
        ]

    def __str__(self):
        return f"{self.cto.nome} - {self.get_situacao_display()} ({self.criado_em:%d/%m/%Y %H:%M})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Regra de negócio central: toda nova ocorrência atualiza o status
        # "atual" da CTO. O histórico em si nunca muda -- só esse espelho.
        CTO.objects.filter(pk=self.cto_id).update(
            status_atual=self.situacao,
            portas_livres_atual=self.portas_livres,
        )

    @staticmethod
    def calcular_situacao_por_portas(portas_livres: int) -> str:
        """
        Threshold de negócio (não é percentual, é baseado em portas livres
        restantes, pra funcionar igual em qualquer capacidade de splitter):
        0 portas livres -> lotada
        <=2 portas livres -> proxima_lotacao
        """
        from django.conf import settings as dj_settings

        if portas_livres <= dj_settings.LIMITE_PORTAS_LIVRES_LOTADA:
            return Situacao.LOTADA
        if portas_livres <= dj_settings.LIMITE_PORTAS_LIVRES_QUASE_LOTADA:
            return Situacao.PROXIMA_LOTACAO
        return Situacao.NORMAL
