# Deploy Cyber Sentinels Website on VPS (IP-only hosting)

Use this guide to run the site on a Linux VPS using only the server IP (no domain).

---

## 1. Replace placeholders

- **YOUR_VPS_IP** = your server’s public IP (e.g. `192.168.1.100`)
- **deploy** = optional Linux user for running the app (you can use `root` or another user)

---

## 2. VPS: update system and install dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx redis-server git
```

---

## 3. Upload your project to the VPS

**Option A – From your PC (with project on disk):**

```bash
# On your PC, from the folder that CONTAINS "Cyber-Sentinels-Website"
scp -r Cyber-Sentinels-Website deploy@YOUR_VPS_IP:~/
```

**Option B – Git (if the project is in a repo):**

```bash
# On VPS
cd ~
git clone YOUR_REPO_URL Cyber-Sentinels-Website
cd Cyber-Sentinels-Website
```

**Option C – Zip and upload:**

```bash
# On PC: create zip (exclude venv, __pycache__, .git if you want)
cd parent_folder
zip -r project.zip Cyber-Sentinels-Website -x "*.pyc" -x "*__pycache__*" -x "*.git*"

# Upload
scp project.zip deploy@YOUR_VPS_IP:~/

# On VPS
cd ~ && unzip project.zip && cd Cyber-Sentinels-Website
```

---

## 4. On VPS: go to project and create virtualenv

```bash
cd ~/Cyber-Sentinels-Website
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Production `.env` on the VPS

Create or edit `.env` in the project root (same folder as `manage.py`):

```bash
nano .env
```

Paste (replace **YOUR_VPS_IP** with your real IP):

```env
DEBUG=False
SECRET_KEY=CHANGE_THIS_TO_A_LONG_RANDOM_STRING
ALLOWED_HOSTS=YOUR_VPS_IP,localhost,127.0.0.1
SITE_BASE_URL=http://YOUR_VPS_IP

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Cyber Sentinels <noreply@yoursite.com>

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
CELERY_BROKER_URL=redis://127.0.0.1:6379/0

# Required for form/API submissions (flag submit, notifications). Use the exact URL(s) users use to open the site.
CSRF_TRUSTED_ORIGINS=http://YOUR_VPS_IP,https://YOUR_VPS_IP
```

Generate a new `SECRET_KEY`:

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Put that value in `.env` as `SECRET_KEY=...`.

---

## 6. Database and static files

```bash
cd ~/Cyber-Sentinels-Website
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

---

## 6b. Start Redis (required when DEBUG=False)

The app uses Redis for cache, WebSockets (notifications), and Celery. If Redis is not running, you may see **"Unexpected response from server"** on flag submission and `redis.exceptions.ConnectionError` in logs.

```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
sudo systemctl status redis-server
```

---

## 7. Test run (optional)

```bash
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

From your PC browser open `http://YOUR_VPS_IP:8000`. If it loads, stop with `Ctrl+C` and continue.

---

## 8. Gunicorn (HTTP only, no WebSockets)

If you **do not** need live WebSockets, use Gunicorn:

```bash
pip install gunicorn
gunicorn --bind 127.0.0.1:8000 Cybersentinels_website.wsgi:application
```

Then in the next steps use **Gunicorn** (port 8000). Skip step 9 and use the Gunicorn systemd service below.

---

## 9. Daphne (HTTP + WebSockets) – recommended if you use Dojo live features

Your app uses Django Channels; for WebSockets use Daphne:

```bash
source venv/bin/activate
daphne -b 127.0.0.1 -p 8000 Cybersentinels_website.asgi:application
```

Leave it running in a terminal to test, or use the systemd service below.

---

## 10. Systemd service (Daphne – app runs on reboot)

Create the service file:

```bash
sudo nano /etc/systemd/system/cybersentinels.service
```

Paste (fix paths and user if needed):

```ini
[Unit]
Description=Cyber Sentinels (Daphne ASGI)
After=network.target redis-server.service

[Service]
User=YOUR_USER
Group=YOUR_USER
WorkingDirectory=/home/YOUR_USER/Cyber-Sentinels-Website
Environment="PATH=/home/YOUR_USER/Cyber-Sentinels-Website/venv/bin"
ExecStart=/home/YOUR_USER/Cyber-Sentinels-Website/venv/bin/daphne -b 127.0.0.1 -p 8000 Cybersentinels_website.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Replace:

- **YOUR_USER** = your Linux username (e.g. `deploy` or `root`)
- **/home/YOUR_USER/Cyber-Sentinels-Website** = full path to the project

If you use **Gunicorn** instead of Daphne, use this `ExecStart`:

```ini
ExecStart=/home/YOUR_USER/Cyber-Sentinels-Website/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 Cybersentinels_website.wsgi:application
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cybersentinels
sudo systemctl start cybersentinels
sudo systemctl status cybersentinels
```

---

## 11. Nginx (reverse proxy and static files)

Create Nginx config:

```bash
sudo nano /etc/nginx/sites-available/cybersentinels
```

Paste (replace **YOUR_VPS_IP** and **/home/YOUR_USER**):

```nginx
server {
    listen 80;
    server_name YOUR_VPS_IP;
    client_max_body_size 50M;

    location /static/ {
        alias /home/YOUR_USER/Cyber-Sentinels-Website/staticfiles/;
    }

    location /media/ {
        alias /home/YOUR_USER/Cyber-Sentinels-Website/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

Enable and reload Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/cybersentinels /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 12. Firewall (allow HTTP)

```bash
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable
sudo ufw status
```

---

## 13. Optional: Celery (background tasks)

If you use Celery/Beat:

```bash
sudo nano /etc/systemd/system/cybersentinels-celery.service
```

```ini
[Unit]
Description=Cyber Sentinels Celery
After=network.target redis-server.service

[Service]
User=YOUR_USER
Group=YOUR_USER
WorkingDirectory=/home/YOUR_USER/Cyber-Sentinels-Website
Environment="PATH=/home/YOUR_USER/Cyber-Sentinels-Website/venv/bin"
ExecStart=/home/YOUR_USER/Cyber-Sentinels-Website/venv/bin/celery -A Cybersentinels_website worker -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo nano /etc/systemd/system/cybersentinels-celerybeat.service
```

```ini
[Unit]
Description=Cyber Sentinels Celery Beat
After=network.target redis-server.service

[Service]
User=YOUR_USER
Group=YOUR_USER
WorkingDirectory=/home/YOUR_USER/Cyber-Sentinels-Website
Environment="PATH=/home/YOUR_USER/Cyber-Sentinels-Website/venv/bin"
ExecStart=/home/YOUR_USER/Cyber-Sentinels-Website/venv/bin/celery -A Cybersentinels_website beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cybersentinels-celery cybersentinels-celerybeat
sudo systemctl start cybersentinels-celery cybersentinels-celerybeat
```

---

## 14. Checklist

| Step | Command / action |
|------|-------------------|
| 1 | Replace **YOUR_VPS_IP** and **YOUR_USER** everywhere |
| 2 | `apt install` → nginx, python3-venv, redis-server |
| 3 | Upload project to VPS |
| 4 | `python3 -m venv venv` and `pip install -r requirements.txt` |
| 5 | Create `.env` with `DEBUG=False`, `ALLOWED_HOSTS=YOUR_VPS_IP`, `SITE_BASE_URL`, `CSRF_TRUSTED_ORIGINS`, Redis vars |
| 6 | `migrate`, `collectstatic`, `createsuperuser`; **start Redis**: `sudo systemctl start redis-server` |
| 7 | Run Daphne or Gunicorn manually to test |
| 8 | Create and start systemd service |
| 9 | Configure Nginx and reload |
| 10 | `ufw allow 80` and enable firewall |

---

## 15. Open in browser

- **Club site:** `http://YOUR_VPS_IP/`
- **Dojo (CTF):** `http://YOUR_VPS_IP/dojo/`
- **Admin:** `http://YOUR_VPS_IP/admin/`

---

## Troubleshooting

- **502 Bad Gateway:** App not running. Check: `sudo systemctl status cybersentinels` and logs: `journalctl -u cybersentinels -f`
- **Static files 404:** Run `python manage.py collectstatic --noinput` and check `alias` path in Nginx.
- **"Unexpected response from server" on flag submit / 403 Forbidden:** (1) **Redis must be running** when `DEBUG=False` (cache and WebSockets use it). Start it: `sudo systemctl start redis-server && sudo systemctl enable redis-server`. (2) Set **CSRF_TRUSTED_ORIGINS** in `.env` to the URL(s) users use (e.g. `CSRF_TRUSTED_ORIGINS=http://YOUR_VPS_IP,https://YOUR_VPS_IP`). Then restart the app: `sudo systemctl restart cybersentinels`.
- **Redis ConnectionError (Error 111) in logs:** Redis is not running or not reachable. Install if needed: `sudo apt install redis-server`, then `sudo systemctl start redis-server`.
- **CSRF / redirect issues:** In `.env`, set `SITE_BASE_URL=http://YOUR_VPS_IP`, add your IP to `ALLOWED_HOSTS`, and set `CSRF_TRUSTED_ORIGINS=http://YOUR_VPS_IP,https://YOUR_VPS_IP`.
- **WebSockets not working:** Use Daphne (step 9) and the Daphne systemd service; keep `proxy_set_header Upgrade` and `Connection "upgrade"` in Nginx.
