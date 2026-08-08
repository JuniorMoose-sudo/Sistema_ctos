"""
Importa CTOs por município a partir das PASTAS do KMZ de cobertura Proxxima.

O KMZ agrupa os placemarks em pastas por município (ex.: "Lagoa Seca - PB (412)").
Cada placemark da pasta é uma CTO daquele município — o filtro por "CTO" no nome
estava errado (cidades como Lagoa Seca usam nomes "LGC-...", Queimadas "CGED-...",
sem a substring "CTO").

Regras:
- Reatribui `cidade` de CTOs existentes pela pasta em que o nome aparece.
- Remove CTOs não-Campina cujo nome NÃO está em nenhuma pasta-alvo (ex.: as 179 de
  "Esperança" importadas por bbox que na verdade são de Areial).
- Importa todos os placemarks das pastas-alvo ainda não cadastrados.
- Campina Grande só ganha CTOs realmente novas da pasta (2 no KMZ atual); as
  existentes não são alteradas.

Uso:
    python manage.py importar_cidades /caminho/para/Area_de_cobertura.kmz
"""
import re
import zipfile
from collections import defaultdict
from xml.etree import ElementTree as ET

from django.core.management.base import BaseCommand, CommandError

from ctos.models import CTO

NS = "{http://www.opengis.net/kml/2.2}"

MUNICIPIOS = [
    "Campina Grande", "Lagoa Seca", "Puxinanã", "Pocinhos",
    "Esperança", "Alagoa Nova", "Itatuba", "Massaranduba", "Montadas",
    "Serra Redonda", "Riachão do Bacamarte", "São Sebastião de Lagoa de Roça",
    "Queimadas",
]


def municipio_da_pasta(nome_pasta):
    return re.sub(r"\s*-\s*[A-Z]{2}\s*\(\d+\)\s*$", "", nome_pasta).strip()


class Command(BaseCommand):
    help = "Importa/reconcilia CTOs por município a partir das pastas do KMZ de cobertura."

    def add_arguments(self, parser):
        parser.add_argument("caminho_kmz", type=str)

    def handle(self, *args, **options):
        try:
            with zipfile.ZipFile(options["caminho_kmz"]) as z:
                with z.open("doc.kml") as f:
                    tree = ET.parse(f)
        except (zipfile.BadZipFile, KeyError, FileNotFoundError) as exc:
            raise CommandError(f"Não foi possível abrir o KMZ: {exc}")

        # nome do placemark -> (município, lat, lon)
        nome_para_cidade = {}
        por_cidade = defaultdict(int)
        for doc in tree.getroot().iter(NS + "Document"):
            for folder in doc.findall(NS + "Folder"):
                mun = municipio_da_pasta(folder.findtext(NS + "name", "?"))
                if mun not in MUNICIPIOS:
                    continue
                for pm in folder.findall(".//" + NS + "Placemark"):
                    nome = (pm.findtext(NS + "name", "") or "").strip()
                    if not nome:
                        continue
                    coords_el = pm.find(".//" + NS + "coordinates")
                    if coords_el is None or not coords_el.text:
                        continue
                    try:
                        lon, lat = (float(x) for x in coords_el.text.strip().split(",")[:2])
                    except ValueError:
                        continue
                    nome_para_cidade[nome] = (mun, lat, lon)
                    por_cidade[mun] += 1

        nomes_db = dict(CTO.objects.values_list("nome", "cidade"))
        self.stdout.write(f"{len(nomes_db)} CTOs no banco | pastas-alvo: {dict(por_cidade)}")

        # ---- 1) Reatribui cidade das existentes pela pasta ----
        a_reatribuir = [
            (nome, mun_pasta)
            for nome, cidade_atual in nomes_db.items()
            for mun_pasta in [nome_para_cidade.get(nome, (None,))[0] if nome in nome_para_cidade else None]
            if mun_pasta is not None and mun_pasta != cidade_atual
        ]
        if a_reatribuir:
            for nome, mun in a_reatribuir:
                CTO.objects.filter(nome=nome).update(cidade=mun)
            self.stdout.write(self.style.WARNING(
                f"Reatribuídas {len(a_reatribuir)} CTOs pela pasta (ex.: {a_reatribuir[:5]})"
            ))

        # ---- 2) Remove não-Campina que não está em nenhuma pasta-alvo ----
        removidas = []
        for pk, nome, cidade in CTO.objects.exclude(cidade="Campina Grande").values_list("pk", "nome", "cidade"):
            if nome not in nome_para_cidade:
                removidas.append((pk, nome, cidade))
        if removidas:
            CTO.objects.filter(pk__in=[r[0] for r in removidas]).delete()
            self.stdout.write(self.style.ERROR(
                f"Removidas {len(removidas)} CTOs fora das pastas-alvo "
                f"(ex.: {[(r[1], r[2]) for r in removidas[:5]]})"
            ))

        # ---- 3) Importa placemarks novos das pastas-alvo ----
        a_importar = [
            (nome, mun, lat, lon)
            for nome, (mun, lat, lon) in nome_para_cidade.items()
            if nome not in nomes_db
        ]
        if a_importar:
            CTO.objects.bulk_create(
                [
                    CTO(nome=nome, latitude=lat, longitude=lon, bairro=None, cidade=mun)
                    for nome, mun, lat, lon in a_importar
                ],
                batch_size=1000,
            )
            self.stdout.write(self.style.SUCCESS(f"Importadas {len(a_importar)} CTOs novas."))
        else:
            self.stdout.write("Nenhuma CTO nova para importar.")
