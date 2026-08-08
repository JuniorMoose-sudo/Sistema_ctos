# Sistema de Monitoramento de CTOs Lotadas — Campina Grande

Sistema Django/DRF (API + app do técnico) com dashboard Streamlit, banco Neon
(Postgres serverless). Especificação completa em `spec_sistema_ctos_lotadas.md`.

## 1. Ambiente

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     Linux:  source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # Windows  (Linux: cp .env.example .env)
# edite o .env (DATABASE_URL do Neon, SECRET_KEY, etc.)
```

## 2. Banco (Neon)

Crie um projeto no [Neon](https://neon.tech), copie a connection string para
`DATABASE_URL` no `.env`. O `sslmode=require` já está fixo no `settings.py`.

```bash
cd backend
python manage.py migrate
python manage.py createsuperuser   # acesso ao /admin/
```

## 3. Importar dados

```bash
# CTOs de Campina + municípios vizinhos (a partir das pastas do KMZ de cobertura):
python manage.py importar_cidades "..\data\Área de cobertura Proxxima Telecomunicações S.A. 29.07.2026.kmz"

# Técnicos (cria os usuários a partir de um JSON — veja data/tecnicos.exemplo.json):
python manage.py importar_tecnicos ..\data\tecnicos.json
```

## 4. Produção (Windows + waitress)

O backend é servido por **waitress** (WSGI puro, sem dependência de serviços
Linux). Dois processos:

```powershell
# Backend + admin + app do técnico em http://<ip>:8000
.\scripts\iniciar_backend.ps1

# Dashboard do gestor em http://<ip>:8501
.\scripts\iniciar_dashboard.ps1
```

Para **produção real**:

1. Edite o `.env`:
   - `DEBUG=False`
   - `SECRET_KEY` com valor forte (`python -c "import secrets; print(secrets.token_urlsafe(50))"`)
   - `ALLOWED_HOSTS` com o domínio/IP público
   - `CSRF_TRUSTED_ORIGINS` com o domínio (ex.: `https://sistema.suaempresa.com.br`)
   - `USE_HTTPS=True` se houver TLS (Nginx/Let's Encrypt) na frente
2. Rode `python manage.py check --deploy` para revisar a configuração.
3. Exponha as portas 8000 (API) e 8501 (dashboard) no firewall.

> **App do técnico em campo:** `navigator.geolocation` só funciona em **HTTPS**
> ou `localhost`. No celular, o domínio precisa ter certificado (Let's Encrypt),
> senão o GPS não é capturado (o app usa busca por nome como fallback).

## Variáveis de ambiente (`.env`)

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `DATABASE_URL` | sim | Connection string do Neon |
| `SECRET_KEY` | sim (com `DEBUG=False`) | Chave do Django |
| `DEBUG` | — | `True` só em desenvolvimento |
| `ALLOWED_HOSTS` | — | Hosts permitidos, separados por vírgula |
| `CSRF_TRUSTED_ORIGINS` | — | Origens para POSTs via browser (domínio) |
| `USE_HTTPS` | — | `True` atrás de TLS |
| `NOMINATIM_USER_AGENT` | — | User-Agent do script de geocodificação |
| `API_BASE_URL` | — | URL da API usada pelo dashboard (padrão `http://localhost:8000/api`) |
| `API_TOKEN` | — | Token de gestor usado pelo dashboard |

## Endpoints

- Admin: `/admin/`
- App do técnico: `/tecnico/` (login: `/tecnico/login/`)
- API:
  - `POST /api/auth/token/` — login (email/senha) → token
  - `GET /api/ctos/` — visão consolidada (status atual de cada CTO)
  - `GET /api/ctos/buscar/?q=` — busca por nome
  - `GET /api/ctos/proximas/?lat=&lon=` — CTOs próximas ao GPS
  - `GET|POST /api/ocorrencias/` — histórico e lançamento de ocorrências
