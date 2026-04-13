# Operations Runbook

This runbook covers day-to-day operations of a Consensia instance running on a Raspberry Pi: service management, log access, database backup, application updates, and troubleshooting.

---

## Service Management

Consensia runs as a systemd service (`consensia.service`) behind nginx.

### Check service status

```bash
sudo systemctl status consensia
```

Look for `Active: active (running)`. If it shows `failed` or `inactive`, see [Troubleshooting](#troubleshooting).

### Start / stop / restart

```bash
sudo systemctl start consensia
sudo systemctl stop consensia
sudo systemctl restart consensia
```

### Restart nginx

```bash
sudo systemctl restart nginx
```

Test the nginx configuration before restarting:

```bash
sudo nginx -t
```

### Enable / disable on boot

```bash
sudo systemctl enable consensia    # start automatically on reboot
sudo systemctl disable consensia   # do not start on reboot
```

---

## Logs

### Application logs (FastAPI / Gunicorn)

```bash
journalctl -u consensia -f              # stream live
journalctl -u consensia --since today   # today's logs
journalctl -u consensia -n 100          # last 100 lines
```

### nginx logs

```bash
sudo tail -f /var/log/nginx/error.log   # error log
sudo tail -f /var/log/nginx/access.log  # access log
```

### Filtering for errors

```bash
journalctl -u consensia -p err          # error-level and above
journalctl -u consensia | grep "ERROR"  # application-level errors
```

---

## Database Backup

### What to back up

Consensia's persistent state lives in two locations:

| Path | Contents |
|---|---|
| `backend/data/knowledge.db` | All ideas, users, books, tags, votes (SQLite) |
| `backend/data/embeddings/` | ChromaDB vector index (reconstructable) |
| `backend/data/toc.json` | TOC cache (reconstructable) |

The SQLite file is the **source of truth**. The ChromaDB index and TOC cache can always be regenerated from it. Back up at minimum the SQLite file.

### Manual backup

```bash
# Stop the service to ensure a consistent snapshot
sudo systemctl stop consensia

# Copy the data directory
cp -r ~/consensia/backend/data ~/consensia-backup-$(date +%Y%m%d)

# Restart the service
sudo systemctl start consensia
```

For a live backup without stopping the service, use SQLite's online backup:

```bash
sqlite3 ~/consensia/backend/data/knowledge.db ".backup '/tmp/knowledge-backup.db'"
```

### Automated backup (cron)

Add a daily cron job:

```bash
crontab -e
```

```cron
0 2 * * * sqlite3 /home/youruser/consensia/backend/data/knowledge.db ".backup '/home/youruser/backups/knowledge-$(date +\%Y\%m\%d).db'" && find /home/youruser/backups -name "knowledge-*.db" -mtime +30 -delete
```

This backs up at 2 AM and retains the last 30 days.

### Restore from backup

```bash
sudo systemctl stop consensia
cp /path/to/backup/knowledge-20250101.db ~/consensia/backend/data/knowledge.db
sudo systemctl start consensia

# Optionally regenerate the ChromaDB index from the restored SQLite data
cd ~/consensia/backend
source venv/bin/activate
python data_handler.py -e
```

---

## Updating the Application

### Standard update procedure

```bash
# 1. On your development machine — build the new frontend
cd frontend
npm install
VITE_API_URL=https://yourdomain.com/api npm run build
git add frontend/dist
git commit -m "build: updated frontend"
git push

# 2. On the Raspberry Pi
cd ~/consensia
git pull

# 3. Copy new frontend build to nginx's document root
sudo cp -r frontend/dist/* /var/www/html/consensia/

# 4. Update backend dependencies (if requirements.txt changed)
cd backend
source venv/bin/activate
pip install -r requirements.txt

# 5. Restart the backend service
sudo systemctl restart consensia

# 6. Verify
sudo systemctl status consensia
curl http://localhost:8000/health
```

### Rollback

```bash
git log --oneline -10   # find the last good commit hash
git checkout <hash>     # check out that version
# rebuild frontend and redeploy as above
```

---

## Adding a New User

```bash
cd ~/consensia/backend
source venv/bin/activate
python authenticator.py newuser@example.com
```

The command prints a provisioning URI (and optionally a QR code URL). Send it to the new user — they scan it with Google Authenticator to set up their TOTP.

To create an admin user, use the Admin Panel in the web interface (recommended) or set `is_admin = 1` directly in the database.

---

## Regenerating the Vector Index

If the ChromaDB index becomes inconsistent with SQLite (e.g., after a restore or model change):

```bash
cd ~/consensia/backend
source venv/bin/activate
python data_handler.py -e
```

This re-embeds all ideas currently in SQLite and rewrites the ChromaDB collection. It may take several minutes depending on the number of ideas and hardware speed.

---

## Monitoring

### Resource usage

ChromaDB and the SentenceTransformer model are memory-intensive. Check current usage:

```bash
htop                           # interactive process monitor
free -h                        # memory overview
df -h                          # disk space
```

Expected memory profile on Raspberry Pi 4:
- Gunicorn idle: ~200–400 MB
- During TOC generation (ML pipeline): peaks at 1–2 GB
- ChromaDB index: scales with number of ideas (typically < 200 MB for thousands of ideas)

### Service watchdog

systemd automatically restarts the service if it crashes (default `Restart=on-failure`). To confirm the restart policy:

```bash
systemctl show consensia | grep Restart
```

---

## Troubleshooting

### `Illegal Instruction` on startup

**Cause:** PyTorch is not compatible with the aarch64 CPU on Raspberry Pi 4.

**Fix:**

```bash
cd ~/consensia/backend
source venv/bin/activate
pip install torch==2.6.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu
sudo systemctl restart consensia
```

---

### 502 Bad Gateway

**Cause:** nginx cannot reach Gunicorn (service is down or listening on the wrong port).

**Check:**

```bash
sudo systemctl status consensia          # is it running?
curl http://localhost:8000/health        # does it respond?
sudo journalctl -u consensia -n 50       # look for startup errors
```

**Common causes:**
- `JWT_SECRET_KEY` not set — service starts but crashes immediately
- Python dependency missing — add it and restart
- Port conflict — another process on 8000

---

### 403 / 404 for the frontend

**Cause:** nginx cannot find the static files.

**Check:**

```bash
ls /var/www/html/consensia/     # should contain index.html and assets/
sudo nginx -t                   # config syntax check
```

**Fix:**

```bash
sudo cp -r ~/consensia/frontend/dist/* /var/www/html/consensia/
sudo systemctl restart nginx
```

---

### CORS errors in the browser

**Cause:** The frontend's `VITE_API_URL` does not match what is listed in `backend/data/site.json`.

**Check:** Open browser DevTools → Network tab → find a failed request → look at the error. Then:

```bash
cat ~/consensia/backend/data/site.json
```

Ensure your domain (with correct scheme — `https://` vs `http://`) is in the `origins` array.

**Fix:** Update `site.json`, then restart the service:

```bash
sudo systemctl restart consensia
```

---

### JWT errors / users can't log in

**Symptom:** Login returns 401 even with the correct OTP.

**Check the JWT secret:**

```bash
sudo systemctl show consensia -p Environment | tr ' ' '\n' | grep JWT_SECRET_KEY
```

This prints the value systemd will inject into the service. If it is missing or empty, edit the unit file (`sudo systemctl edit --full consensia.service`), make sure the `[Service]` section contains `Environment="JWT_SECRET_KEY=..."`, then `sudo systemctl daemon-reload && sudo systemctl restart consensia`.

**Check OTP sync:**

The OTP is time-based — if the Pi's clock is wrong, TOTP validation will fail.

```bash
timedatectl status               # check system time
sudo timedatectl set-ntp true    # enable NTP if disabled
```

---

### TOC is empty or stale

**Symptom:** Table of Contents shows nothing or outdated content after adding ideas.

**Fix:** Go to the TOC page in the app and click **Update Structure**. Or call the API directly:

```bash
curl -X POST https://yourdomain.com/api/toc/update \
  -H "Authorization: Bearer <your-token>"
```

> Note: This can take 30–120 seconds on a Raspberry Pi 4.
