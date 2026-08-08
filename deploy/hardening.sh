#!/usr/bin/env bash
# =============================================================================
# Hardening do servidor EC2 Ubuntu (mi-ia).
# - Atualizações + segurança automática
# - Firewall UFW (apenas 22/80/443)
# - Fail2ban (SSH + Nginx)
# - SSH: somente chave, sem root, sem senha, acesso limitado ao usuário
# - Nginx: esconde versão
# - Limites de recursos via systemd (anti-crypto-miner descontrolado)
# - Auditoria de portas/processos suspeitos + rkhunter/lynis
#
# Uso (no servidor):  sudo bash deploy/hardening.sh
#
# IMPORTANTE: mantenha o terminal atual aberto enquanto testa uma NOVA sessão
# SSH após a etapa 4 (por segurança, não feche a sessão que já está logada).
# =============================================================================
set -euo pipefail

ALLOW_USERS="${SUDO_USER:-ubuntu}"

echo "==> [1/8] Atualizações + segurança automática"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq unattended-upgrades ufw fail2ban rkhunter lynis curl htop
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> [2/8] Firewall UFW (SSH 22, HTTP 80, HTTPS 443)"
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose

echo "==> [3/8] Fail2ban (SSH + Nginx)"
cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true

[nginx-botsearch]
enabled = true
EOF
systemctl enable fail2ban
systemctl restart fail2ban

echo "==> [4/8] SSH: apenas chave, sem root, sem senha (usuário: $ALLOW_USERS)"
if sshd -t; then
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
    sed -i 's/^#\?PermitEmptyPasswords.*/PermitEmptyPasswords no/' /etc/ssh/sshd_config
    sed -i 's/^#\?MaxAuthTries.*/MaxAuthTries 3/' /etc/ssh/sshd_config
    if ! grep -q '^AllowUsers' /etc/ssh/sshd_config; then
        echo "AllowUsers $ALLOW_USERS" >> /etc/ssh/sshd_config
    else
        sed -i "s/^AllowUsers.*/AllowUsers $ALLOW_USERS/" /etc/ssh/sshd_config
    fi
    systemctl reload ssh
    echo "    Configuração SSH aplicada. Teste uma nova sessão antes de fechar esta."
else
    echo "    AVISO: 'sshd -t' falhou. NÃO apliquei mudanças no SSH."
fi

echo "==> [5/8] Nginx: esconder versão"
if ! grep -q 'server_tokens off' /etc/nginx/nginx.conf; then
    sed -i '/^http {/a\    server_tokens off;' /etc/nginx/nginx.conf
    nginx -t && systemctl reload nginx
fi

echo "==> [6/8] Limites de recursos por serviço (evita minerador consumir a máquina)"
mkdir -p /etc/systemd/system/sistema-ctos-backend.service.d
cat > /etc/systemd/system/sistema-ctos-backend.service.d/limits.conf <<'EOF'
[Service]
MemoryMax=700M
CPUQuota=200%
TasksMax=40
EOF
mkdir -p /etc/systemd/system/sistema-ctos-dashboard.service.d
cat > /etc/systemd/system/sistema-ctos-dashboard.service.d/limits.conf <<'EOF'
[Service]
MemoryMax=700M
CPUQuota=100%
TasksMax=40
EOF
systemctl daemon-reload

echo "==> [7/8] Auditoria de exposição e processo suspeito (mineradores)"
echo "--- Portas escutando (procure serviços inesperados, ex.: 3000=Grafana, 2375/2376=Docker): ---"
ss -tulpn
echo ""
echo "--- Top 10 processos por CPU: ---"
ps aux --sort=-%cpu | head -10
echo ""
echo "--- Binários executáveis em /tmp e /var/tmp: ---"
find /tmp /var/tmp -maxdepth 2 -type f -executable 2>/dev/null | head -20
echo ""
echo "--- Crontabs do sistema e usuários (procure coisas estranhas): ---"
for u in $(cut -d: -f1 /etc/passwd); do
    c=$(crontab -l -u "$u" 2>/dev/null)
    [ -n "$c" ] && echo "# $u:" && echo "$c"
done
ls -la /etc/cron.d/ 2>/dev/null
echo ""

echo "==> [8/8] Rkhunter (integridade) + Lynis (auditoria)"
rkhunter --propupd >/dev/null 2>&1 || true
rkhunter --check --sk >/dev/null 2>&1 || true
echo "    Log de integridade: /var/log/rkhunter.log"
echo "    Relatório completo: sudo lynis audit system"

echo ""
echo "FIM. Próximos passos fora do script:"
echo "  1) AWS Console > EC2 > Security Group: permitir inbound APENAS 22, 80, 443."
echo "     Ideal: porta 22 só para o seu IP fixo (ex.: <SEU_IP>/32)."
echo "  2) Troque a senha do dashboard:  sudo htpasswd /etc/nginx/.htpasswd_sistema gestor"
echo "  3) Revogue/regere tokens antigos no /admin/ (os que já apareceram no terminal)."
echo "  4) Auditoria completa:  sudo lynis audit system"
