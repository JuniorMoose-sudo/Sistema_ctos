# Deploy na AWS EC2 (Ubuntu + Nginx + systemd)

Guia completo para subir o Sistema de CTOs na instância **MI-IA** usando a chave `.pem`.
Acesso externo é feito via **IP + nip.io** (sem comprar domínio): ex. `sistema.3.145.20.10.nip.io`.

## Visão geral da arquitetura

```
Internet → Nginx (:80/:443)
             ├── sistema.<IP>.nip.io   → gunicorn (Django) 127.0.0.1:8000
             │      └── /static/ e /media/ servidos direto pelo Nginx
             └── dashboard.<IP>.nip.io → Streamlit 127.0.0.1:8501 (Basic Auth + WebSocket)
```

Os serviços rodam como `www-data` via systemd, com `Restart=always`.

---

## 1. Acesso SSH (Windows + chave .pem)

Do PowerShell (o OpenSSH do Windows já suporta `-i`):

```powershell
ssh -i "C:\caminho\para\sua-chave.pem" ubuntu@<IP-PUBLICO>
```

Dicas:
- A chave `.pem` **não precisa** de `chmod 400` no Windows (isso é só no Linux/Mac).
- No Linux/WSL, use `chmod 400 sua-chave.pem` antes do `ssh`.
- Se não quiser digitar a chave toda vez, crie `~/.ssh/config`:

```
Host mi-ia
    HostName <IP-PUBLICO>
    User ubuntu
    IdentityFile C:\caminho\para\sua-chave.pem
```

E então basta `ssh mi-ia`.

## 2. Enviar o código para o servidor

O projeto está versionado em https://github.com/JuniorMoose-sudo/Sistema_ctos.git, então
basta **clonar** no servidor (sem precisar copiar arquivo por arquivo):

```bash
sudo git clone https://github.com/JuniorMoose-sudo/Sistema_ctos.git /opt/sistema_ctos
```

Se preferir SSH em vez de HTTPS (recomendado, para `git pull` sem senha depois):

```bash
sudo git clone git@github.com:JuniorMoose-sudo/Sistema_ctos.git /opt/sistema_ctos
```

> No seu PC (Windows): rode `git init`, `git add .`, commit e `git push -u origin main`
> na pasta `sistema_ctos` para publicar o código no repositório. O `.gitignore` já exclui
> `.env`, `db.sqlite3`, `media/`, `staticfiles/`, `logs/` e `.venv/`.

## 3. Instalar e subir (roda UMA vez no servidor)

```bash
# entre no servidor (passo 1). O projeto já está clonado em /opt/sistema_ctos.
cd /opt/sistema_ctos

# rode o deploy (use o IP público real da instância)
sudo bash deploy/deploy.sh 3.145.20.10
```

O script:
1. Instala `python3-venv`, `nginx`, `apache2-utils` (htpasswd) e `certbot`.
2. Cria o venv e instala o `requirements.txt`.
3. Cria o `/opt/sistema_ctos/.env` a partir do `deploy/.env.production.example` (**não sobrescreve um `.env` existente**).
4. Roda `migrate` e `collectstatic`.
5. Ajusta permissões para `www-data`.
6. Instala os dois sites no Nginx e protege o dashboard com Basic Auth (`gestor` / `troque-esta-senha`).
7. Instala e inicia os serviços systemd `sistema-ctos-backend` (gunicorn :8000) e `sistema-ctos-dashboard` (Streamlit :8501).

## 4. Configurar o `.env` de produção

```bash
sudo nano /opt/sistema_ctos/.env
```

Preencha:
- `DATABASE_URL` com a string do Neon **sem** `channel_binding=require` (só `sslmode=require` no Linux).
- `API_TOKEN` com o token do usuário gestor (o mesmo do dashboard Windows: `d9f82e767b3846934149bbeeeb592f656e6bf555`, do usuário `admin`).
- `NOMINATIM_USER_AGENT` com seu e-mail.

Depois recarregue os serviços:

```bash
sudo systemctl restart sistema-ctos-backend sistema-ctos-dashboard
```

Verificações úteis:

```bash
sudo systemctl status sistema-ctos-backend sistema-ctos-dashboard
sudo journalctl -u sistema-ctos-backend -n 30 --no-pager
sudo journalctl -u sistema-ctos-dashboard -n 30 --no-pager
```

## 5. HTTPS (Let's Encrypt + nip.io)

O nip.io resolve `qualquercoisa.<IP>.nip.io` para o IP público, então o Let's Encrypt aceita
o desafio HTTP-01 normalmente — **sem precisar de domínio próprio**:

```bash
sudo certbot --nginx -d sistema.<IP>.nip.io -d dashboard.<IP>.nip.io
```

Depois de obter os certificados, ligue as proteções HTTPS do Django:

```bash
sudo sed -i 's/^USE_HTTPS=False/USE_HTTPS=True/' /opt/sistema_ctos/.env
sudo systemctl restart sistema-ctos-backend
```

> Obs.: o `USE_HTTPS=True` liga `SECURE_SSL_REDIRECT` etc. Ele fica `False` durante o deploy
> porque antes do certbot não existe listener HTTPS.

## 6. Validação final

```bash
# local
curl -s http://127.0.0.1:8000/api/ctos/?limit=1 -H "Authorization: Token <API_TOKEN>" | head -c 300
curl -s http://127.0.0.1:8501/_stcore/health          # deve responder ok

# externo (de qualquer lugar)
curl -s https://sistema.<IP>.nip.io/api/ctos/?limit=1 -H "Authorization: Token <API_TOKEN>"
```

Acesse:
- Backend/admin: `https://sistema.<IP>.nip.io/admin` (user `admin`)
- App do técnico: `https://sistema.<IP>.nip.io/tecnico/`
- Dashboard: `https://dashboard.<IP>.nip.io` (user `gestor`) — com HTTPS, o **geoposition** do app do técnico funciona.

## Atualizações futuras (após uma mudança no código)

```bash
cd /opt/sistema_ctos
sudo git pull                          # ou `sudo git pull origin main`
/opt/sistema_ctos/.venv/bin/pip install -r requirements.txt
cd backend && /opt/sistema_ctos/.venv/bin/python manage.py migrate --noinput
/opt/sistema_ctos/.venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart sistema-ctos-backend sistema-ctos-dashboard
```

## Rollback

```bash
sudo systemctl stop sistema-ctos-backend sistema-ctos-dashboard
sudo rm /etc/nginx/sites-enabled/ctos-backend /etc/nginx/sites-enabled/ctos-dashboard
sudo systemctl reload nginx
```
