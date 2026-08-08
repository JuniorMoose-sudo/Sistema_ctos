"""
Importa técnicos a partir de um arquivo JSON.

Formato esperado (tecnicos.json):
[
    {"usuario": "joao.silva", "senha": "troque-no-primeiro-acesso"},
    {"usuario": "carlos.souza", "senha": "troque-no-primeiro-acesso"}
]

A senha é hasheada no momento do import (nunca fica em texto puro no banco).
Também cria automaticamente um token de API (DRF) para cada técnico, já que
o app do técnico se autentica via TokenAuthentication.

Uso:
    python manage.py importar_tecnicos /caminho/para/tecnicos.json
"""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework.authtoken.models import Token

User = get_user_model()


class Command(BaseCommand):
    help = "Importa técnicos (usuário/senha) de um arquivo JSON."

    def add_arguments(self, parser):
        parser.add_argument("caminho_json", type=str)

    def handle(self, *args, **options):
        caminho = options["caminho_json"]

        try:
            with open(caminho, encoding="utf-8") as f:
                tecnicos = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise CommandError(f"Não foi possível ler o JSON: {exc}")

        criados, existentes = 0, 0

        for item in tecnicos:
            usuario = item.get("usuario")
            senha = item.get("senha")
            if not usuario or not senha:
                self.stdout.write(self.style.WARNING(f"Registro inválido, pulando: {item}"))
                continue

            user, criado = User.objects.get_or_create(username=usuario)
            if criado:
                user.set_password(senha)  # hasheada, nunca texto puro
                user.save()
                Token.objects.get_or_create(user=user)
                criados += 1
            else:
                existentes += 1

        self.stdout.write(self.style.SUCCESS(
            f"Concluído: {criados} técnicos criados, {existentes} já existiam (não alterados)."
        ))
