from rest_framework import serializers

from ctos.models import CTO, Ocorrencia


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


class OcorrenciaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ocorrencia
        fields = [
            "cto", "situacao", "motivo", "portas_usadas", "portas_livres",
            "foto", "observacao", "latitude_registro", "longitude_registro",
        ]

    def create(self, validated_data):
        validated_data["tecnico"] = self.context["request"].user
        return super().create(validated_data)


class OcorrenciaListSerializer(serializers.ModelSerializer):
    nome_cto = serializers.CharField(source="cto.nome", read_only=True)
    bairro = serializers.CharField(source="cto.bairro", read_only=True)
    tecnico_username = serializers.CharField(source="tecnico.username", read_only=True)

    class Meta:
        model = Ocorrencia
        fields = [
            "id", "nome_cto", "bairro", "situacao", "motivo",
            "portas_usadas", "portas_livres", "tecnico_username",
            "observacao", "latitude_registro", "longitude_registro", "criado_em",
        ]
