from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt

from django.db.models import OuterRef, Subquery
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.response import Response
from rest_framework.views import APIView

from ctos.models import CTO, Ocorrencia

from .serializers import CTOSerializer, OcorrenciaCreateSerializer, OcorrenciaListSerializer

RAIO_TERRA_METROS = 6371000


def haversine_metros(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return RAIO_TERRA_METROS * 2 * atan2(sqrt(a), sqrt(1 - a))


class ObterTokenView(APIView):
    """
    POST /api/auth/token/
    Login do técnico. Não usa SessionAuthentication (authentication_classes
    vazio), então funciona mesmo quando o navegador tem cookie de sessão do
    /admin/ -- sem exigir CSRF token no body.
    """

    authentication_classes = ()
    permission_classes = ()
    throttle_classes = ()
    serializer_class = AuthTokenSerializer

    def post(self, request):
        serializer = AuthTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username})


class CTOsProximasView(APIView):
    """
    GET /api/ctos/proximas/?lat=&lon=
    Retorna as 3 CTOs mais próximas do ponto informado.
    Usado no primeiro passo do fluxo do técnico (antes da confirmação).
    """

    def get(self, request):
        try:
            lat = float(request.query_params["lat"])
            lon = float(request.query_params["lon"])
        except (KeyError, ValueError):
            return Response(
                {"detail": "Parâmetros 'lat' e 'lon' são obrigatórios e devem ser numéricos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pré-filtro por bounding box (~±0.03° ≈ ±3 km) para reduzir o número
        # de CTOs antes do cálculo exato em Python. Se a caixa ficar vazia ou
        # com menos de 3 candidatas (ex.: ponto isolado no interior), faz
        # fallback para a varredura completa — mantém o resultado exato.
        margem = 0.03
        candidatas = self._calcular_distancias(
            lat, lon, lat - margem, lat + margem, lon - margem, lon + margem
        )
        if len(candidatas) < 3:
            candidatas = self._calcular_distancias(lat, lon)

        candidatas.sort(key=lambda c: c.distancia_metros)
        top3 = candidatas[:3]

        serializer = CTOSerializer(top3, many=True)
        return Response(serializer.data)

    @staticmethod
    def _calcular_distancias(lat, lon, lat_min=None, lat_max=None, lon_min=None, lon_max=None):
        qs = CTO.objects.filter(ativa=True).only(
            "id", "nome", "latitude", "longitude", "bairro",
            "capacidade", "splitter", "status_atual", "portas_livres_atual",
        )
        if lat_min is not None:
            qs = qs.filter(
                latitude__range=(lat_min, lat_max),
                longitude__range=(lon_min, lon_max),
            )
        candidatas = []
        for cto in qs:
            distancia = haversine_metros(lat, lon, float(cto.latitude), float(cto.longitude))
            cto.distancia_metros = round(distancia, 1)
            candidatas.append(cto)
        return candidatas


class CTOsBuscarView(generics.ListAPIView):
    """
    GET /api/ctos/buscar/?q=
    Fallback para quando o GPS falha -- busca por nome.
    """

    serializer_class = CTOSerializer

    def get_queryset(self):
        termo = self.request.query_params.get("q", "")
        return CTO.objects.filter(ativa=True, nome__icontains=termo)[:20]


class CTOListView(generics.ListAPIView):
    """
    GET /api/ctos/
    Visão consolidada para o gestor: todas as CTOs com o status_atual
    (espelho da última ocorrência) e a data da última ocorrência.

    Filtros: ?bairro=&status=&q=
    """

    serializer_class = CTOSerializer

    def get_queryset(self):
        ultima_ocorrencia = (
            Ocorrencia.objects.filter(cto=OuterRef("pk"))
            .order_by("-criado_em")
            .values("criado_em")[:1]
        )
        qs = (
            CTO.objects.filter(ativa=True)
            .annotate(ultima_ocorrencia=Subquery(ultima_ocorrencia))
            .order_by("nome")
        )
        params = self.request.query_params
        if bairro := params.get("bairro"):
            qs = qs.filter(bairro=bairro)
        if status_filtro := params.get("status"):
            qs = qs.filter(status_atual=status_filtro)
        if q := params.get("q"):
            qs = qs.filter(nome__icontains=q)
        return qs

    def list(self, request, *args, **kwargs):
        # Otimização de performance: evita o ModelSerializer (custoso para
        # 5.744 registros) e serializa direto do ORM. `ultima_ocorrencia` é
        # annotation e sobrevive ao .values(). O dashboard é o único
        # consumidor deste endpoint e não usa capacidade/splitter.
        qs = self.filter_queryset(self.get_queryset())
        campos = [
            "id", "nome", "latitude", "longitude", "bairro", "cidade",
            "capacidade", "splitter", "status_atual",
            "portas_livres_atual", "ultima_ocorrencia",
        ]
        return Response(list(qs.values(*campos)))


class CTODetalheView(generics.RetrieveAPIView):
    """GET /api/ctos/<id>/ -- cadastro + status atual."""

    queryset = CTO.objects.all()
    serializer_class = CTOSerializer


class OcorrenciaListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/ocorrencias/?cto=&bairro=&data_inicio=&data_fim=&situacao=
         Usado pelo dashboard Streamlit (KPIs, mapa, ranking) e exportação CSV.
    POST /api/ocorrencias/
         Registro do técnico em campo.
    """

    def get_serializer_class(self):
        return OcorrenciaCreateSerializer if self.request.method == "POST" else OcorrenciaListSerializer

    def get_queryset(self):
        qs = Ocorrencia.objects.select_related("cto", "tecnico")
        params = self.request.query_params

        if cto_id := params.get("cto"):
            qs = qs.filter(cto_id=cto_id)
        if bairro := params.get("bairro"):
            qs = qs.filter(cto__bairro=bairro)
        if situacao := params.get("situacao"):
            qs = qs.filter(situacao=situacao)

        # Filtro por data SEM função na coluna (criado_em__date=...) para o
        # índice de criado_em ser aproveitado. data_inicio é inclusivo;
        # data_fim também, via < (data_fim + 1 dia).
        for param, gte in (("data_inicio", True), ("data_fim", False)):
            if valor := params.get(param):
                try:
                    data = datetime.strptime(valor, "%Y-%m-%d")
                except ValueError:
                    continue
                if gte:
                    qs = qs.filter(criado_em__gte=data)
                else:
                    qs = qs.filter(criado_em__lt=data + timedelta(days=1))

        return qs
