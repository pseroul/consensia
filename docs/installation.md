# Installation Guide

This guide covers two scenarios:

- **Option A** — Local development setup (your laptop or desktop)
- **Option B** — Production deployment on a Raspberry Pi 4

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.12 also works |
| Node.js | 20+ | LTS recommended |
| npm | 10+ | Bundled with Node 20 |
| git | any | For cloning the repo |
| nginx | any | Production only |

**Hardware (production):** Raspberry Pi 4 (aarch64, 4 GB RAM recommended due to ChromaDB's memory footprint).

---

## Option A: Local Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/pseroul/consensia.git
cd consensia
```

### 2. Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note (Raspberry Pi / aarch64 only):** If `import torch` raises `Illegal Instruction`, install a compatible CPU build:
> ```bash
> pip install torch==2.6.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu
> ```

#### Create the data directory

```bash
mkdir -p data
```

#### Configure CORS origins

Create `backend/data/site.json`:

```json
{
  "origins": [
    "http://localhost:5173",
    "http://127.0.0.1:5173"
  ]
}
```

#### Set the JWT secret key

The server requires a secret key to sign authentication tokens. Export it in your shell (or add to your `.bashrc` / `.zshrc`):

```bash
export JWT_SECRET_KEY="replace-with-a-long-random-string"
```

Generate a secure value with:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### Add the first user

Consensia uses TOTP (Google Authenticator) — there are no passwords. To create your first account:

```bash
python authenticator.py your@email.com
```

The command prints a provisioning URI. Open it in a QR-code renderer or paste it directly into Google Authenticator → **Set up account** → **Enter a setup key**.

#### Start the backend

```bash
python main.py
```

The API is now available at `http://localhost:8000`.  
Swagger UI: `http://localhost:8000/docs`

### 3. Frontend setup

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The app is now available at `http://localhost:5173`.

---

## Option B: Raspberry Pi Production Deployment

This section walks through a complete, from-scratch production setup on a Raspberry Pi 4.

### Step 1 — Flash and configure the Pi

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/) and flash **Raspberry Pi OS Lite (64-bit)** to an SD card.
2. In the imager's advanced options, enable SSH and set your username/password.
3. Insert the SD card, boot the Pi, and SSH in:

```bash
ssh youruser@<pi-ip-address>
```

> **Tip:** Assign your Pi a static IP via your router's DHCP reservation settings, or configure it in `/etc/dhcpcd.conf`. This makes the deployment URL stable.

### Step 2 — Update the system

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

### Step 3 — Install system dependencies

```bash
sudo apt-get install -y git python3.11 python3.11-venv python3-pip nginx
```

Install Node.js 20 via NodeSource:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Verify:

```bash
python3.11 --version   # Python 3.11.x
node --version         # v20.x.x
nginx -v               # nginx/1.x.x
```

### Step 4 — Open firewall ports

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

Also forward ports **80** and **443** on your home router to the Pi's local IP address (consult your router's documentation).

### Step 5 — Clone the repository

```bash
cd ~
git clone https://github.com/pseroul/consensia.git
cd consensia
```

### Step 6 — Backend setup

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **aarch64 PyTorch fix:** If startup fails with `Illegal Instruction`:
> ```bash
> pip install torch==2.6.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu
> ```

Create the data directory:

```bash
mkdir -p data
```

Create `backend/data/site.json` — include your domain (and localhost for testing):

```json
{
  "origins": [
    "http://localhost:5173",
    "https://yourdomain.com",
    "http://yourdomain.com"
  ]
}
```

Generate a JWT secret key — keep the printed value, you will paste it into the systemd unit file in [Step 10](#step-10--create-the-systemd-service):

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Add the first admin user:

```bash
source venv/bin/activate
python authenticator.py admin@yourdomain.com
```

Scan the printed QR code with Google Authenticator.

### Step 7 — Build the frontend

> **Do this on your development machine** (not the Pi), to avoid installing Node.js on the server.

```bash
cd frontend
npm install
VITE_API_URL=https://yourdomain.com/api npm run build
```

> If you are using an IP address instead of a domain, use `http://<your-public-ip>/api`.

Commit and push the built output so the Pi can pull it:

```bash
git add frontend/dist
git commit -m "build: production frontend"
git push
```

Back on the Pi, pull the build:

```bash
cd ~/consensia
git pull
```

### Step 8 — Deploy the frontend

```bash
sudo mkdir -p /var/www/html/consensia
sudo rm -rf /var/www/html/consensia/*
sudo cp -r frontend/dist/* /var/www/html/consensia/
```

### Step 9 — Configure nginx

Create the nginx site configuration:

```bash
sudo nano /etc/nginx/sites-available/consensia
```

Paste the following (replace `your_public_ip_address` with your Pi's public IP or domain name):

```nginx
server {
    listen 80;
    server_name your_public_ip_address;

    # Frontend (React SPA)
    location / {
        root /var/www/html/consensia;
        index index.html;
        try_files $uri /index.html;
    }

    # Backend (FastAPI) via reverse proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable the site and restart nginx:

```bash
sudo ln -s /etc/nginx/sites-available/consensia /etc/nginx/sites-enabled/
sudo nginx -t          # verify config is valid
sudo systemctl restart nginx
```

### Step 10 — Create the systemd service

This runs Gunicorn as a persistent background service that restarts on failure and starts on boot.

```bash
sudo nano /etc/systemd/system/consensia.service
```

Paste (replace `youruser` with your actual username):

```ini
[Unit]
Description=Gunicorn instance to serve Consensia
After=network.target

[Service]
User=youruser
WorkingDirectory=/home/youruser/consensia/backend
Environment="PATH=/home/youruser/consensia/backend/venv/bin"
Environment="JWT_SECRET_KEY=paste-the-secret-from-step-6-here"
ExecStart=/home/youruser/consensia/backend/venv/bin/gunicorn \
    -w 1 \
    -k uvicorn.workers.UvicornWorker \
    main:app \
    --bind 127.0.0.1:8000

[Install]
WantedBy=multi-user.target
```

> Optional LLM env vars (`ANTHROPIC_API_KEY`, `OLLAMA_URL`, `OLLAMA_MODEL`, `LLM_MODEL`) go in the same `[Service]` section as additional `Environment=` lines. See [LLM Backends for Table of Contents](#optional-llm-backends-for-table-of-contents) below.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable consensia.service
sudo systemctl start consensia.service
```

### Step 11 — Verify the deployment

```bash
# Service is running
sudo systemctl status consensia

# Backend responds
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# nginx serves the frontend
curl -I http://localhost
# Expected: HTTP/1.1 200 OK
```

Open `http://<your-public-ip>` in a browser, log in with your email and the OTP from Google Authenticator.

---

## Optional: LLM Backends for Table of Contents

Consensia can generate book-like chapter titles and a narrative reading order for its Table of Contents using an LLM. This is **entirely optional** — without any LLM backend, the system automatically falls back to a TF-IDF keyword extractor that always works.

The backend selects an LLM at startup in this priority order:

1. **Claude API** — if `ANTHROPIC_API_KEY` is set (best quality)
2. **Ollama** — if a local server responds on `OLLAMA_URL` (offline, free)
3. **TF-IDF** — always available (zero external dependencies)

You can configure either option below (or both — Claude will be tried first). See [data-science.md](data-science.md#llm-powered-title-generation) for how the pipeline uses these backends.

---

### Option 1: Claude API (recommended)

The Anthropic Claude API offers the best title quality and narrative ordering. It is a paid service, but TOC generation uses small prompts with the cheapest model (`claude-haiku-4-5-20251001`), so real-world cost is usually a few cents per month for a personal instance.

#### 1. Create an Anthropic account

Go to [console.anthropic.com](https://console.anthropic.com) and sign up with an email address. You will need to verify your email and add a payment method before you can generate a key.

#### 2. Add credits

Claude API is prepaid. Navigate to **Plans & Billing → Buy credits** and add a small amount (e.g. $5) — this is more than enough for months of Consensia usage.

#### 3. Generate an API key

1. In the console, go to **Settings → API Keys**
2. Click **Create Key**
3. Give it a descriptive name (e.g. `consensia-rpi-prod`)
4. Copy the key — it starts with `sk-ant-api03-...`. **You cannot view it again** after closing the dialog.

#### 4. Configure the backend

**Local development** — export the key in your shell (or add it to `~/.bashrc` / `~/.zshrc`):

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

**Raspberry Pi (production)** — edit the Consensia systemd unit file so the key is scoped to the service:

```bash
sudo systemctl edit --full consensia.service
```

Add an `Environment=` line in the `[Service]` section:

```ini
[Service]
Environment="ANTHROPIC_API_KEY=sk-ant-api03-..."
```

Optionally override the default model on another line (only needed if you want a different Claude variant):

```ini
Environment="LLM_MODEL=claude-haiku-4-5-20251001"
```

Reload and restart the service to apply:

```bash
sudo systemctl daemon-reload
sudo systemctl restart consensia
```

#### 5. Verify

Check the backend logs for the LLM init message:

```bash
journalctl -u consensia -n 50 | grep -i llm
# Expected: "ClaudeLlmClient initialised (model=claude-haiku-4-5-20251001)"
```

Then trigger a TOC rebuild from the app (TOC page → **Update Structure**) and confirm the chapter titles look like book titles rather than keyword lists.

---

### Option 2: Ollama (local, offline)

If you prefer to keep all inference on-device — for privacy, zero cost, or air-gapped deployments — Ollama runs small language models locally. On a Raspberry Pi 5 with 16 GB RAM, a 3B-parameter model (e.g. `phi3:mini` or `llama3.2:3b`) produces acceptable titles with a generation time of roughly 5–15 seconds per TOC refresh.

> **Hardware note:** Vanilla Ollama runs on the CPU only. If you own a Raspberry Pi AI HAT+ 2 (Hailo-10H, 40 TOPS), see [Sub-option 2b](#sub-option-2b-hardware-accelerated-with-hailo-10h-ai-hat-2) below for a hardware-accelerated drop-in replacement.

#### 1. Install Ollama on the Raspberry Pi

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

The installer creates an `ollama` user, registers a systemd service (`ollama.service`), and starts it listening on `127.0.0.1:11434`.

Verify it is running:

```bash
systemctl status ollama
curl http://localhost:11434/api/tags
# Expected: {"models":[]}
```

#### 2. Pull a model

Small models work best on Raspberry Pi. `phi3:mini` (3.8B params, ~2.3 GB) is the default:

```bash
ollama pull phi3:mini
```

Alternatives to consider (trade-offs between quality and speed):

| Model | Size | RAM needed | Notes |
|---|---|---|---|
| `phi3:mini` | ~2.3 GB | ~4 GB | Fast, small, decent quality — default |
| `llama3.2:3b` | ~2.0 GB | ~4 GB | Good instruction-following |
| `qwen2.5:3b` | ~1.9 GB | ~4 GB | Strong at structured output (JSON) |
| `gemma2:2b` | ~1.6 GB | ~3 GB | Fastest — use if the above are slow |

Pull with:

```bash
ollama pull <model-name>
```

#### 3. Configure the backend to use Ollama

If `ANTHROPIC_API_KEY` is **not** set, Consensia will probe `OLLAMA_URL` (default `http://localhost:11434`) at startup and automatically use it if reachable. You only need to set environment variables if you customised the installation.

**Local development:**

```bash
export OLLAMA_URL="http://localhost:11434"
export OLLAMA_MODEL="phi3:mini"
```

**Raspberry Pi (production)** — edit the Consensia unit file:

```bash
sudo systemctl edit --full consensia.service
```

Add these two lines to the `[Service]` section:

```ini
Environment="OLLAMA_URL=http://localhost:11434"
Environment="OLLAMA_MODEL=phi3:mini"
```

Then reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart consensia
```

#### 4. Verify

```bash
journalctl -u consensia -n 50 | grep -i llm
# Expected: "OllamaLlmClient initialised (url=http://localhost:11434, model=phi3:mini)"
```

#### 5. Memory considerations

Ollama loads the model into memory on first inference and keeps it resident for a few minutes. On a Raspberry Pi 5 with 16 GB RAM, running Consensia + ChromaDB + Ollama + `phi3:mini` comfortably fits within budget. On smaller Pis (4 GB), prefer Claude API or the TF-IDF fallback.

Check usage during a TOC refresh:

```bash
free -h
htop
```

---

### Sub-option 2b: Hardware-accelerated with Hailo-10H (AI HAT+ 2)

Since the launch of the **Raspberry Pi AI HAT+ 2** (January 2026), Hailo ships an Ollama-compatible runtime called **`hailo-ollama`** that offloads LLM inference to the 40 TOPS Hailo-10H NPU and its 8 GB of dedicated on-board RAM. It uses the same REST API as vanilla Ollama, so Consensia's existing `OllamaLlmClient` works without any code changes — only environment variables change.

Benefits vs. CPU Ollama on a Pi 5:

- Inference offloaded to the NPU — the 4 ARM cores stay free for FastAPI, ChromaDB, and the UMAP pipeline
- Models live in the 8 GB of VRAM on the HAT — no pressure on the Pi's system RAM
- TOC generation drops from 5–15 s down to a few seconds on small models

> **Prerequisite:** this path assumes you already completed [Option B — Raspberry Pi Production Deployment](#option-b-raspberry-pi-production-deployment) and have a Raspberry Pi AI HAT+ 2 physically installed. Follow the [AI HAT+ 2 setup in the Raspberry Pi docs](https://www.raspberrypi.com/documentation/computers/ai.html) to verify the NPU is detected (`hailortcli fw-control identify`).

#### 1. Install the Hailo Gen-AI Model Zoo

Download the GenAI runtime package from the [Hailo Developer Zone](https://hailo.ai/developer-zone/) (free registration required) — pick the `arm64` build matching your Raspberry Pi OS / Ubuntu version. Then install it:

```bash
sudo dpkg -i hailo_gen_ai_model_zoo_5.1.1_arm64.deb
sudo apt-get install -f   # in case any dependency is missing
```

This installs the `hailo-ollama` binary and the tools to pull pre-compiled models from the Hailo Gen-AI Model Zoo.

#### 2. Start the `hailo-ollama` server

```bash
hailo-ollama serve
```

By default the server listens on **port 8000**, which clashes with Consensia's backend. On a box that runs both, you must pick one of these:

- **Recommended** — run `hailo-ollama` on a different port (e.g. `11434` to mimic vanilla Ollama):
  ```bash
  HAILO_OLLAMA_PORT=11434 hailo-ollama serve
  ```
- **Alternative** — move Consensia's backend to another port by editing `--bind 127.0.0.1:8001` in `/etc/systemd/system/consensia.service` and updating the `proxy_pass` in the nginx site file.

To run `hailo-ollama` as a persistent service, create `/etc/systemd/system/hailo-ollama.service`:

```ini
[Unit]
Description=Hailo Ollama server (Hailo-10H NPU)
After=network.target

[Service]
User=youruser
Environment="HAILO_OLLAMA_PORT=11434"
ExecStart=/usr/bin/hailo-ollama serve
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hailo-ollama.service
```

#### 3. Pull a model from the Hailo Gen-AI Model Zoo

Only models pre-compiled for the Hailo-10H NPU are available. At the time of writing, the Model Zoo includes small instruction-tuned models such as `qwen2:1.5b`, `qwen2.5:3b`, `phi3:mini`, and `llama3.2:3b`.

```bash
hailo-ollama pull qwen2:1.5b
```

> **Note:** the exact list of supported tags evolves with each Model Zoo release. Run `hailo-ollama list` after installation to see what is currently available on your system, and check [Hailo's Model Zoo documentation](https://hailo.ai/developer-zone/documentation/) for the current catalogue.

#### 4. Verify the server responds

```bash
curl http://localhost:11434/api/tags
# Expected: {"models":[{"name":"qwen2:1.5b", ...}]}
```

#### 5. Configure Consensia

Because `hailo-ollama` speaks the Ollama REST API, just point `OLLAMA_URL` at it. Edit the Consensia unit file:

```bash
sudo systemctl edit --full consensia.service
```

In the `[Service]` section, add:

```ini
Environment="OLLAMA_URL=http://localhost:11434"
Environment="OLLAMA_MODEL=qwen2:1.5b"
```

Make sure there is **no** `Environment="ANTHROPIC_API_KEY=..."` line (or that it is empty) so the factory in `backend/llm_client.py` falls through to the Ollama backend. Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart consensia
journalctl -u consensia -n 50 | grep -i llm
# Expected: "OllamaLlmClient initialised (url=http://localhost:11434, model=qwen2:1.5b)"
```

Trigger a TOC rebuild from the app (**TOC → Update Structure**) and you should see NPU load jump on the Hailo device:

```bash
hailortcli monitor
```

#### 6. Fallback behaviour

The Hailo-accelerated path is transparent to the rest of the code. If `hailo-ollama` stops or the NPU hangs, Consensia's `OllamaLlmClient` will raise `LlmUnavailableError`, the `TfidfFallbackClient` takes over, and the TOC still regenerates — just with keyword-style titles. No manual intervention needed.

---

### Falling back to TF-IDF only

If you set neither `ANTHROPIC_API_KEY` nor run Ollama, Consensia uses the built-in TF-IDF keyword extractor. This requires no configuration and produces short keyword-based titles (e.g. `"Machine Learning & Hardware"`). No action needed — this is the default.

---

## Optional: HTTPS with a Custom Domain

> **Requires a domain name.** IP-only deployments cannot use Certbot.

### 1. Register a domain and configure DNS

Buy a domain from any registrar (OVH, Namecheap, Cloudflare, etc.). Then:

- Go to your registrar's DNS settings
- Set the **A record** for `yourdomain.com` and `www.yourdomain.com` to your Pi's public IP address
- Wait for DNS propagation (up to 24 h, usually minutes)

### 2. Update nginx to use the domain

Edit `/etc/nginx/sites-available/consensia` — replace `server_name`:

```nginx
server_name yourdomain.com www.yourdomain.com;
```

Also rebuild the frontend with the new URL:

```bash
# On your dev machine:
VITE_API_URL=https://yourdomain.com/api npm run build
git add frontend/dist && git commit -m "build: update API URL to domain" && git push

# On the Pi:
git pull
sudo cp -r frontend/dist/* /var/www/html/consensia/
```

### 3. Issue the TLS certificate

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot automatically rewrites the nginx configuration to redirect HTTP → HTTPS and serves the certificate.

### 4. Close the HTTP port (optional but recommended)

```bash
sudo ufw delete allow 80/tcp
sudo ufw reload
```

Certbot sets up automatic renewal via a systemd timer — no further action needed.

---

## Updating the Application

See [operations.md](operations.md#updating-the-application) for the standard update procedure.
