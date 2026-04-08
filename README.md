
# Consensia
This application allows the management and the retrieval of ideas in order to find ideas by similarity, sort them, create contents for presentation or reports. 
It contains two different services: 
- backend: a fastapi server managing data that run on port 8000
- frontend: a react.js interface to access the backend. 

# Backend
See [how to install and run backend](/backend/README.md)

# Frontend
See [how to install and run frontend](/frontend/README.md)

# Deployment in production
## Configure your router and Pi
- Open firewall and forward port 80 (http) & 443 (https) on your router (look at your router documentation)
- Open your Raspberry Pi port 80 (http) & 443 (https):
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```


## Install and run nginx
nginx is use as a gateway to serve your website (both backend and frontend).
```bash
sudo apt install nginx
```

Configure nginx to serve your application
- Create file */etc/nginx/sites-available/consensia* and paste the following code:
```bash
server {
    listen 80;
    server_name [your_public_ip_address];

    # 1. Front-end (React)
    location / {
        root /var/www/html/consensia;
        index index.html;
        try_files $uri /index.html;
    }

    # 2. Backend (FastAPI) via Proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000/; # Redirect to local Gunicorn 
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
  - Add symbolic link to unabled site
```bash
sudo ln -s /etc/nginx/sites-available/consensia /etc/nginx/sites-enabled/
```
  - Restart nginx
```bash
sudo systemctl restart nginx
```

## Install and run Gunicorn for FastAPI on your system (prod server)
Gunicorn is a production server that restarts by itself if something bad append. By creating a service, we also allow for Gunicorn to restart when your server restart.
 To go into production, use gunicorn.

```bash
sudo nano /etc/systemd/system/consensia.service
```
With file content:
```bash
[Unit]
Description=Gunicorn instance to serve Consensia
After=network.target

[Service]
User=[your user]
WorkingDirectory=/home/[your user]/consensia/backend
Environment="PATH=/home/[your user]/consensia/backend/venv/bin"
ExecStart=/home/[your user]/consensia/backend/venv/bin/gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app --bind 127.0.0.1:8000

[Install]
WantedBy=multi-user.target
```

Then restart the service
```bash
sudo systemctl daemon-reload
sudo systemctl restart consensia.service
```

Allow the server to launch the service after reboot: 
```bash
sudo systemctl enable consensia.service
```

## Use a domain name instead of a public IP
Go to OVH and: 
- Buy a domain name
- Configure the DNS: 
  - Go to Zone DNS
  - Select your domain
  - Change the 'A' type entries target by your public IP address. 

In your nginx configuration file, replace your **[your_public_ip_address]** by **[your_domain_name]**.

## Use certificates for HTTPS connection
> Warning: this is only feasible if you have a domain name and not a public IP address.

1. Modify nginx
In */etc/nginx/sites-enabled/consensia* replace `server_name [your_public_ip_address];`with `server_name [your_domain.com] [www.yourdomain.com];`.

2. Install and run Certbot:
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d [your_domain.com]
```
Skip email address settings...

Certbot rewrites your nginx configuration with the appropriate certificates.

3. Close http port:
```bash
sudo ufw delete allow 80/tcp
sudo ufw reload
```
