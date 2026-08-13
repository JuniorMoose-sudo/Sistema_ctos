"""
Fase 0 do projeto -- bloqueante para todo o resto.

Lê o .kmz, extrai nome + coordenadas de cada Placemark (o arquivo NÃO tem
bairro/capacidade/splitter -- confirmado por inspeção direta do XML), faz
geocodificação reversa via Nominatim para descobrir o bairro, e faz upsert
na tabela CTO por nome.

Uso:
    python manage.py importar_kmz /caminho/para/Campina_Grande_-_PB_5743.kmz
    python manage.py importar_kmz /caminho/para/Guarabira-PB.kmz --cidade "Guarabira"

Notas importantes:
- Nominatim exige um User-Agent identificável (política deles) e rate limit
  de 1 requisição/segundo -- para 5.743 CTOs isso leva ~1h40. Rodar em
  background (nohup / screen / tmux), não interativo.
- O comando faz cache em memória por (lat, lon) arredondado, e é seguro
  rodar de novo (upsert por nome) se cair no meio.
- KML usa a ordem longitude,latitude nas coordinates -- atenção pra não
  inverter.
"""
import time
import zipfile
from xml.etree import ElementTree as ET

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ctos.models import CTO

KML_NAMESPACE = {"kml": "http://www.opengis.net/kml/2.2"}
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


class Command(BaseCommand):
    help = "Importa CTOs de um arquivo .kmz e geocodifica o bairro via Nominatim."

    def add_arguments(self, parser):
        parser.add_argument("caminho_kmz", type=str)
        parser.add_argument(
            "--sem-geocodificacao",
            action="store_true",
            help="Importa só nome/lat/long, pulando a chamada ao Nominatim (útil para teste rápido).",
        )
        parser.add_argument(
            "--cidade",
            type=str,
            default=None,
            help="Cidade das CTOs importadas (ex.: 'João Pessoa', 'Guarabira').",
        )

    def handle(self, *args, **options):
        caminho_kmz = options["caminho_kmz"]
        pular_geo = options["sem_geocodificacao"]
        cidade = options["cidade"]

        placemarks = self._extrair_placemarks(caminho_kmz)
        total = len(placemarks)
        self.stdout.write(f"{total} CTOs encontradas no KMZ.")

        cache_bairro = {}
        criadas, atualizadas, falhas_geo = 0, 0, 0

        for i, (nome, lat, lon) in enumerate(placemarks, start=1):
            defaults = {"latitude": lat, "longitude": lon, "cidade": cidade}
            if not pular_geo:
                chave_cache = (round(lat, 4), round(lon, 4))
                if chave_cache in cache_bairro:
                    bairro = cache_bairro[chave_cache]
                else:
                    bairro = self._geocodificar(lat, lon)
                    cache_bairro[chave_cache] = bairro
                    if bairro is None:
                        falhas_geo += 1
                    time.sleep(1)  # respeita o rate limit do Nominatim (1 req/s)
                if bairro is not None:
                    defaults["bairro"] = bairro  # falha de geo não apaga bairro já cadastrado

            _, criado = CTO.objects.update_or_create(
                nome=nome,
                defaults=defaults,
            )
            criadas += int(criado)
            atualizadas += int(not criado)

            if i % 100 == 0 or i == total:
                self.stdout.write(f"  ... {i}/{total} processadas")

        self.stdout.write(self.style.SUCCESS(
            f"Concluído: {criadas} criadas, {atualizadas} atualizadas, "
            f"{falhas_geo} sem bairro (geocodificação falhou -- ok, não é bloqueante)."
        ))

    def _extrair_placemarks(self, caminho_kmz):
        try:
            with zipfile.ZipFile(caminho_kmz) as z:
                with z.open("doc.kml") as f:
                    tree = ET.parse(f)
        except (zipfile.BadZipFile, KeyError, FileNotFoundError) as exc:
            raise CommandError(f"Não foi possível abrir o KMZ: {exc}")

        resultados = []
        for placemark in tree.getroot().iter("{http://www.opengis.net/kml/2.2}Placemark"):
            nome_el = placemark.find("kml:name", KML_NAMESPACE)
            coords_el = placemark.find(".//kml:coordinates", KML_NAMESPACE)
            if nome_el is None or coords_el is None or not coords_el.text:
                continue

            nome = nome_el.text.strip()
            # KML: "longitude,latitude,altitude"
            partes = coords_el.text.strip().split(",")
            if len(partes) < 2:
                continue
            longitude, latitude = float(partes[0]), float(partes[1])
            resultados.append((nome, latitude, longitude))

        return resultados

    def _geocodificar(self, lat, lon):
        # Retenta com backoff exponencial quando o Nominatim devolve 429
        # (rate limit). Só desiste (None) depois de várias tentativas.
        for tentativa in range(5):
            try:
                resp = requests.get(
                    NOMINATIM_URL,
                    params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 16},
                    headers={"User-Agent": settings.NOMINATIM_USER_AGENT},
                    timeout=10,
                )
                if resp.status_code == 429:
                    espera = 10 * (tentativa + 1)
                    self.stdout.write(f"    429 (rate limit): aguardando {espera}s e retentando...")
                    time.sleep(espera)
                    continue
                resp.raise_for_status()
                dados = resp.json()
                endereco = dados.get("address", {})
                # Nominatim varia o campo dependendo da região: tenta os mais comuns.
                return (
                    endereco.get("suburb")
                    or endereco.get("neighbourhood")
                    or endereco.get("quarter")
                    or endereco.get("city_district")
                )
            except (requests.RequestException, ValueError):
                return None
        return None
