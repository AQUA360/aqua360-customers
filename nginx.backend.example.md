server {
    listen 443 ssl;
    server_name demo-exploitation.api-customers.example.com;

    ssl_certificate /etc/nginx/ssl/origin.pem;
    ssl_certificate_key /etc/nginx/ssl/origin.key;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        # Static servit des del host (bind mount Docker -> host)
        alias /var/www/aqua360-customers/docker-data/static/;
    }

    location /media/ {
        # Media servit des del host (bind mount Docker -> host)
        alias /var/www/aqua360-customers/docker-data/media/;
    }

    location / {
        include proxy_params;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
        # Backend Docker exposat amb BACKEND_PORT=8000
        proxy_pass http://127.0.0.1:8000;
    }

    error_log /var/log/nginx/customers-backend-error.log;
    access_log /var/log/nginx/customers-backend-access.log;

    client_max_body_size 20M;


}
