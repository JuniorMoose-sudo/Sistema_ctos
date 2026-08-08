#!/usr/bin/env bash
# =============================================================================
# Deploy do Sistema de CTOs na AWS EC2 (Ubuntu + Nginx + systemd).
#
# Uso (no servidor, na raiz do projeto copiado para /opt/sistema_ctos):
#   sudo bash deploy/deploy.sh <IP_PUBLICO> [prefixo_backend] [prefixo_dashboard]
#
# Exemplo:
#   sudo bash deploy/deploy.sh 3.145.20.10
#   -> backend:  https://sistema.3.145.20.10.nip.io
#       dashboard: https://dashboard.3.145.20.10.nip.io
# =============================================================================
set -euo pipefail

IP="${1:?Uso: deploy.sh <IP_PUBLICO> [prefixo_backend] [prefixo_dashboard]}"
PREFIXO_BACKEND="${2:-sistema}"
PREFIXO_DASHBOARD="${3:-dashboard}"
HOST_BACKEND="${PREFIXO_BACKEND}.${IP}.nip.io"
HOST_DASHBOARD="${PREFIXO_DASHBOARD}.${IP}.nip.io"

PROJ=/opt/sistema_ctos
VENV="$PROJ/.venv"
ENV_FILE="$PROJ/.env"

echo "==> [1/8] Dependências do sistema (python3-venv, nginx, apache2-utils, certbot)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip nginx apache2-utils certbot python3-certbot-nginx

echo "==> [2/8] Ambiente virtual + requirements"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$PROJ/requirements.txt" -q

echo "==> [3/8] .env (só é criado se ainda não existir — não sobrescreve o seu)"
if [ ! -f "$ENV_FILE" ]; then
    cp "$PROJ/deploy/.env.production.example" "$ENV_FILE"
    sed -i "s|<SECRET_KEY>|$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 50)|" "$ENV_FILE"
    echo "    ATENÇÃO: edite $ENV_FILE antes de subir (DATABASE_URL, API_TOKEN, NOMINATIM_USER_AGENT)."
else
    echo "    .env existente mantido."
fi
sed -i "s|<IP>|$IP|g" "$ENV_FILE"

echo "==> [4/8] Migrações + collectstatic"
mkdir -p "$PROJ/backend/logs" "$PROJ/backend/media"
cd "$PROJ/backend"
"$VENV/bin/python" manage.py migrate --noinput
"$VENV/bin/python" manage.py collectstatic --noinput

echo "==> [5/8] Permissões (nginx + gunicorn/streamlit rodam como www-data)"
chown -R www-data:www-data "$PROJ"

echo "==> [6/8] Nginx (sites + Basic Auth do dashboard)"
cp "$PROJ/deploy/nginx/ctos-backend.conf" /etc/nginx/sites-available/ctos-backend
cp "$PROJ/deploy/nginx/ctos-dashboard.conf" /etc/nginx/sites-available/ctos-dashboard
sed -i "s|<IP>|$IP|g" /etc/nginx/sites-available/ctos-backend /etc/nginx/sites-available/ctos-dashboard
ln -sf /etc/nginx/sites-available/ctos-backend /etc/nginx/sites-enabled/ctos-backend
ln -sf /etc/nginx/sites-available/ctos-dashboard /etc/nginx/sites-enabled/ctos-dashboard

if [ ! -f /etc/nginx/.htpasswd_sistema ]; then
    htpasswd -cb /etc/nginx/.htpasswd_sistema gestor "troque-esta-senha"
    echo "    Dashboard protegido com usuário 'gestor'. Troque a senha:"
    echo "      sudo htpasswd /etc/nginx/.htpasswd_sistema gestor"
fi
nginx -t
systemctl reload nginx

echo "==> [7/8] Systemd (gunicorn na 8000 + Streamlit na 8501)"
cp "$PROJ/deploy/systemd/sistema-ctos-backend.service" /etc/systemd/system/
cp "$PROJ/deploy/systemd/sistema-ctos-dashboard.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sistema-ctos-backend.service
systemctl enable --now sistema-ctos-dashboard.service

echo "==> [8/8] Próximos passos"
echo ""
echo " 1) Preencha $ENV_FILE (DATABASE_URL do Neon, API_TOKEN, NOMINATIM_USER_AGENT)."
echo " 2) Habilite o HTTPS (o nip.io resolve para o IP público, então o Let's Encrypt aceita):"
echo "      sudo certbot --nginx -d $HOST_BACKEND -d $HOST_DASHBOARD"
echo " 3) Depois de obter os certificados, ligue as proteções HTTPS do Django:"
echo "      sudo sed -i 's/^USE_HTTPS=False/USE_HTTPS=True/' $ENV_FILE"
echo "      sudo systemctl restart sistema-ctos-backend"
echo ""
echo "Pronto! Backend: http://$HOST_BACKEND  |  Dashboard: http://$HOST_DASHBOARD (user: gestor)"
