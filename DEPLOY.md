# Deploy na VPS — Aurora by Develoi

Guia completo para subir a Aurora em produção no Ubuntu.

---

## Requisitos da VPS

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| RAM | 8 GB | 16 GB |
| Disco | 20 GB livres | 40 GB |
| CPU | 2 vCPUs | 4 vCPUs |
| OS | Ubuntu 20.04+ | Ubuntu 22.04 LTS |

> A Hostinger KVM 2 (8 GB RAM, 2 vCPUs) atende com folga usando `qwen2.5:3b`.

---

## 1. Acesso à VPS

```bash
ssh usuario@IP_DA_VPS
```

---

## 2. Dependências do sistema

```bash
sudo apt update && sudo apt upgrade -y

# Python, pip, venv, git
sudo apt install -y python3 python3-pip python3-venv git

# FFmpeg (obrigatório para transcrição de áudio)
sudo apt install -y ffmpeg

# Nginx e Certbot (SSL)
sudo apt install -y nginx certbot python3-certbot-nginx

# Utilitários
sudo apt install -y curl wget htop
```

---

## 3. Instalar Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verificar:

```bash
ollama --version
systemctl status ollama
```

Baixar o modelo:

```bash
ollama pull qwen2.5:3b
```

Testar:

```bash
ollama run qwen2.5:3b "Olá, tudo bem?"
```

---

## 4. Clonar o projeto

```bash
cd /opt
sudo git clone https://github.com/SEU_USUARIO/SEU_REPO.git aurora
sudo chown -R $USER:$USER /opt/aurora
cd /opt/aurora
```

---

## 5. Ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 6. Configurar o `.env` de produção

```bash
cp .env.example .env
nano .env
```

Conteúdo recomendado para a KVM 2:

```env
WHISPER_MODEL_SIZE=small
WHISPER_COMPUTE_TYPE=int8
TRANSCRIPTION_TEMP_DIR=tmp
MAX_UPLOAD_SIZE_MB=25

OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_DEFAULT_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=180
OLLAMA_KEEP_ALIVE=10m

TTS_DEFAULT_VOICE=pt_BR-faber-medium
TTS_AVAILABLE_VOICES=pt_BR-faber-medium,pt_BR-edresson-low,pt_BR-cadu-medium,pt_BR-jeff-medium
TTS_DEFAULT_SPEED=1.0
TTS_MAX_TEXT_LENGTH=4000
TTS_AUDIO_TTL_MINUTES=1440

TAVILY_API_KEY=sua_chave_aqui
SEARCH_ENABLED=true
```

> As vozes Edge TTS (Francisca, Thalita, Antonio) funcionam automaticamente — não precisam de configuração extra, só de conexão com internet.

Criar pasta temporária:

```bash
mkdir -p tmp
```

---

## 7. Testar antes de configurar como serviço

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Acesse `http://IP_DA_VPS:8000` para confirmar. Depois `Ctrl+C`.

---

## 8. Serviço systemd — Aurora API

```bash
sudo nano /etc/systemd/system/aurora.service
```

Cole o conteúdo abaixo (ajuste `ubuntu` pelo seu usuário real — veja com `whoami`):

```ini
[Unit]
Description=Aurora by Develoi — AI API
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/aurora
EnvironmentFile=/opt/aurora/.env
ExecStart=/opt/aurora/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Ativar e iniciar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable aurora
sudo systemctl start aurora
sudo systemctl status aurora
```

Ver logs:

```bash
sudo journalctl -u aurora -f
```

---

## 9. Serviço systemd — Ollama

O instalador do Ollama já cria o serviço automaticamente. Apenas garanta que está habilitado:

```bash
sudo systemctl enable ollama
sudo systemctl status ollama
```

---

## 10. Nginx como proxy reverso

```bash
sudo nano /etc/nginx/sites-available/aurora
```

Cole (substituindo `aurora.seudominio.com` pelo seu domínio):

```nginx
server {
    listen 80;
    server_name aurora.seudominio.com;

    client_max_body_size 30M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
        proxy_send_timeout 300s;
    }
}
```

Ativar:

```bash
sudo ln -s /etc/nginx/sites-available/aurora /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 11. SSL com Certbot (HTTPS)

> O DNS do domínio precisa estar apontando para o IP da VPS antes deste passo.

```bash
sudo certbot --nginx -d aurora.seudominio.com
```

Testar renovação automática:

```bash
sudo certbot renew --dry-run
```

Após isso a Aurora estará em `https://aurora.seudominio.com`.

---

## 12. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

> A porta 8000 (uvicorn) e 11434 (Ollama) **não precisam** ser abertas — ficam internas ao servidor.

---

## 13. Atualizar o projeto

```bash
cd /opt/aurora
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart aurora
```

---

## Portas em uso

| Serviço | Porta | Acessível externamente |
|---------|-------|----------------------|
| Uvicorn (FastAPI) | 8000 | Não (só via nginx) |
| Ollama | 11434 | Não (só interno) |
| Nginx HTTP | 80 | Sim (redireciona para HTTPS) |
| Nginx HTTPS | 443 | Sim |
| SSH | 22 | Sim |

---

## Checklist de deploy

- [ ] VPS com Ubuntu 22.04, mínimo 8 GB RAM
- [ ] `ffmpeg` instalado
- [ ] Ollama instalado e `qwen2.5:3b` baixado
- [ ] Projeto clonado em `/opt/aurora`
- [ ] `.env` configurado (incluindo `TAVILY_API_KEY`)
- [ ] Serviço `aurora.service` ativo e habilitado
- [ ] Serviço `ollama.service` ativo e habilitado
- [ ] Nginx configurado e testado (`nginx -t`)
- [ ] DNS do domínio apontando para o IP da VPS
- [ ] SSL emitido com Certbot
- [ ] Firewall UFW configurado
- [ ] Teste final: `curl https://aurora.seudominio.com/health`

---

## Diagnóstico rápido

```bash
# Status dos serviços
sudo systemctl status aurora
sudo systemctl status ollama
sudo systemctl status nginx

# Logs da API
sudo journalctl -u aurora -n 50

# Logs do nginx
sudo tail -f /var/log/nginx/error.log

# Testar API internamente
curl http://127.0.0.1:8000/health

# Testar Ollama
curl http://127.0.0.1:11434/api/tags

# Ver uso de RAM (importante com Ollama)
free -h
```

---

## Uso de RAM esperado (KVM 2)

| Componente | RAM estimada |
|---|---|
| qwen2.5:3b (Ollama) | ~2.5 GB |
| Faster-Whisper small | ~500 MB |
| FastAPI + Uvicorn | ~150 MB |
| Piper TTS | ~200 MB |
| SO + overhead | ~1 GB |
| **Total** | **~4.5 GB** |

Sobram ~3.5 GB de margem nos 8 GB do KVM 2.
