import io
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps
from rest_framework import serializers

from ctos.models import CTO, Ocorrencia


def comprimir_foto(uploaded, max_lado=1280, qualidade=82):
    """Redimensiona/compacta a foto da ocorrência para JPEG (~150-400 KB) e
    corrige a rotação do EXIF. Recebe o arquivo enviado e devolve um
    ContentFile .jpg pronto para o ImageField salvar."""
    img = Image.open(uploaded)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    if max(img.size) > max_lado:
        escala = max_lado / max(img.size)
        img = img.resize(
            (int(img.width * escala), int(img.height * escala)), Image.LANCZOS
        )
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=qualidade, optimize=True)
    nome = Path(uploaded.name).stem or "foto"
    return ContentFile(buf.getvalue(), name=f"{nome}.jpg")


class CoordenadaRegistroField(serializers.DecimalField):
    """DecimalField que arredonda a coordenada para 7 casas decimais (~1 cm)
    antes da validação de max_digits. O GPS do celular envia precisão maior
    (ex.: -7.06378329546781), que não cabe em numeric(10,7)."""

    def to_internal_value(self, data):
        try:
            data = Decimal(str(data)).quantize(
                Decimal("0.0000001"), rounding=ROUND_HALF_UP
            )
        except (InvalidOperation, ValueError, TypeError):
            pass
        return super().to_internal_value(data)


class CTOSerializer(serializers.ModelSerializer):
    distancia_metros = serializers.FloatField(read_only=True, required=False)
    ultima_ocorrencia = serializers.DateTimeField(read_only=True, required=False)

    class Meta:
        model = CTO
        fields = [
            "id", "nome", "latitude", "longitude", "bairro", "cidade",
            "capacidade", "splitter", "status_atual",
            "portas_livres_atual", "distancia_metros", "ultima_ocorrencia",
        ]


class CTOCriarSerializer(serializers.ModelSerializer):
    """Cadastro manual de CTO nova (app do técnico, sem depender do KMZ).

    O nome é validado contra a constraint unique do banco (rejeita duplicata).
    latitude/longitude são arredondadas para 7 casas decimais, igual ao GPS.
    """

    latitude = CoordenadaRegistroField(max_digits=10, decimal_places=7)
    longitude = CoordenadaRegistroField(max_digits=10, decimal_places=7)

    class Meta:
        model = CTO
        fields = [
            "id", "nome", "latitude", "longitude", "bairro", "cidade", "status_atual",
        ]
        read_only_fields = ["id", "status_atual"]


class OcorrenciaCreateSerializer(serializers.ModelSerializer):
    latitude_registro = CoordenadaRegistroField(
        max_digits=10, decimal_places=7, required=False
    )
    longitude_registro = CoordenadaRegistroField(
        max_digits=10, decimal_places=7, required=False
    )

    class Meta:
        model = Ocorrencia
        fields = [
            "cto", "situacao", "motivo", "portas_usadas", "portas_livres",
            "foto", "observacao", "latitude_registro", "longitude_registro",
        ]

    def create(self, validated_data):
        if foto := validated_data.get("foto"):
            validated_data["foto"] = comprimir_foto(foto)
        validated_data["tecnico"] = self.context["request"].user
        return super().create(validated_data)


class OcorrenciaListSerializer(serializers.ModelSerializer):
    nome_cto = serializers.CharField(source="cto.nome", read_only=True)
    bairro = serializers.CharField(source="cto.bairro", read_only=True)
    cidade = serializers.CharField(source="cto.cidade", read_only=True, allow_null=True)
    latitude = serializers.DecimalField(
        source="cto.latitude", max_digits=10, decimal_places=7, read_only=True
    )
    longitude = serializers.DecimalField(
        source="cto.longitude", max_digits=10, decimal_places=7, read_only=True
    )
    tecnico_username = serializers.CharField(source="tecnico.username", read_only=True)

    class Meta:
        model = Ocorrencia
        fields = [
            "id", "nome_cto", "bairro", "cidade", "latitude", "longitude", "situacao", "motivo",
            "portas_usadas", "portas_livres", "tecnico_username",
            "observacao", "latitude_registro", "longitude_registro", "criado_em",
        ]
