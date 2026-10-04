# Eggcellent Eggs

A lightweight Django storefront for a small egg farm. It includes a responsive homepage, product-size enquiries, and email delivery. The database is SQLite, and there is no JavaScript build step.

## Local development

Requires Python 3.10 or newer.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Enquiry emails are printed to the development console by default. To configure a different recipient, set `CONTACT_EMAIL`; for production delivery, configure the `EMAIL_*` variables from `.env.example`. Django does not load `.env` automatically, so set variables in your shell, service environment, or Apache configuration.

Useful checks:

```powershell
python manage.py check
python manage.py test
```

## Raspberry Pi OS and Apache2

These instructions target Raspberry Pi OS 64-bit with Python 3.11+ and Apache `mod_wsgi` built for the same system Python. Do not install `mod_wsgi` into the app virtual environment: use the Debian package so Apache and its module share a compatible Python ABI.

Install system dependencies:

```bash
sudo apt update
sudo apt install -y apache2 libapache2-mod-wsgi-py3 python3-venv python3-pip
sudo mkdir -p /srv/eggcellent
sudo chown "$USER":www-data /srv/eggcellent
```

Copy or clone this project to `/srv/eggcellent`, then set up the application environment:

```bash
cd /srv/eggcellent
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create a production environment file outside the web root, for example `/etc/eggcellent.env`, and restrict access to it. Set a unique `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS` to the Pi's hostname/domain, `CSRF_TRUSTED_ORIGINS` to the full HTTPS origin(s), and valid contact/SMTP settings. For example:

```bash
sudo install -o root -g www-data -m 640 /dev/null /etc/eggcellent.env
sudo nano /etc/eggcellent.env
```

Use the keys in `.env.example`; do not commit real credentials. Django will not read that file by itself. Add `EnvironmentFile` to a systemd-managed Apache service override, or add `SetEnv` entries in the virtual host for non-secret settings. For secrets, a systemd environment file is preferable to placing passwords in the Apache site config. Ensure the Apache process receives those variables after setup.

Initialize Django and prepare static assets:

```bash
cd /srv/eggcellent
. .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
```

Set permissions so Apache can read the source, virtual environment, and static assets, and write the SQLite database and its containing directory. A straightforward single-admin deployment can use `www-data` as the group and grant group write to the project directory/database:

```bash
sudo chgrp -R www-data /srv/eggcellent
sudo chmod -R g+rX /srv/eggcellent
sudo chmod g+w /srv/eggcellent /srv/eggcellent/db.sqlite3
```

If the database does not exist yet, run `migrate` as the same deployment user/group arrangement and then grant the database file appropriate write access. Avoid world-writable permissions.

Edit `deploy/apache-eggs.conf`, replacing `eggs.example.com` with the actual hostname, then enable Apache's WSGI module and the site:

```bash
sudo a2enmod wsgi
sudo cp deploy/apache-eggs.conf /etc/apache2/sites-available/eggs.conf
sudo a2ensite eggs.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Check `/var/log/apache2/eggcellent-error.log` if the site does not load. For public internet use, configure DNS and HTTPS (for example, with Certbot) and redirect HTTP to HTTPS. Keep backups of `db.sqlite3` and the deployment environment file.

## Customization

Update the farm copy and contact recipient in the storefront/template and environment. The two editorial photographs are loaded from Unsplash and require an internet connection; replace their URLs with locally hosted, licensed farm photography for an offline-capable deployment. This starter does not implement payments or stock reservation; the form sends an enquiry email only.
