# Fix: Static files 404 on VPS

## Problem
- Nginx was serving `/static/` from `.../static/` (wrong folder).
- Django's `collectstatic` puts all static files in **`staticfiles/`** (STATIC_ROOT).
- So Nginx must use **`alias .../staticfiles/`** (with trailing slash).

## Fix on your VPS

### 1. Edit Nginx config
```bash
sudo nano /etc/nginx/sites-available/cybersentinels
```

**Replace the entire file with this** (path matches your server):

```nginx
server {
    listen 80;
    server_name 137.97.163.134;
    client_max_body_size 50M;

    # IMPORTANT: Django collectstatic puts files in staticfiles/, not static/
    location /static/ {
        alias /home/cyberdojo/S3NKU/ClubwebisteDOJO/staticfiles/;
    }

    location /media/ {
        alias /home/cyberdojo/S3NKU/ClubwebisteDOJO/media/;
    }

    location / {
        proxy_pass http://unix:/home/cyberdojo/S3NKU/ClubwebisteDOJO/daphne.sock;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_redirect off;
        proxy_read_timeout 86400;
    }
}
```

### 2. Test and reload Nginx
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Ensure collectstatic was run
```bash
cd /home/cyberdojo/S3NKU/ClubwebisteDOJO
source venv/bin/activate
python manage.py collectstatic --noinput
```

### 4. Check staticfiles folder exists and has css/images
```bash
ls -la /home/cyberdojo/S3NKU/ClubwebisteDOJO/staticfiles/
ls -la /home/cyberdojo/S3NKU/ClubwebisteDOJO/staticfiles/css/
ls -la /home/cyberdojo/S3NKU/ClubwebisteDOJO/staticfiles/images/
```

You should see `base.css`, `home.css`, `aboutus.css`, etc. under `staticfiles/css/` and `CyanLogo.png` under `staticfiles/images/`.

### 5. Socket permission (if you still get 502)
Nginx user (often `www-data`) must be able to access the socket. Either:

**Option A – Add nginx user to your group and give group read on socket dir:**
```bash
sudo usermod -a -G cyberdojo www-data
# Then restart Daphne so socket is recreated with correct permissions
sudo systemctl restart cybersentinels
```

**Option B – Use TCP port instead of socket** (simpler):
In your systemd service, change Daphne to bind to `127.0.0.1:8000` instead of the socket file, then in Nginx use `proxy_pass http://127.0.0.1:8000;` instead of `proxy_pass http://unix:.../daphne.sock;`.
