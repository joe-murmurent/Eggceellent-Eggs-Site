# Joe's Trip

Django port of the Next.js trip journal. It provides authenticated sign-in, a 2027 event journal, protected file uploads/downloads, role-based EGGS access, and administration of users, roles, and organizations. The application database is SQLite; MySQL is used only by the one-time legacy import command.

## Local development

Requires Python 3.10 or newer.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. The root page is the sign-in screen; authenticated users land on the trip dashboard. The journal is at `/trip-2027/`. Admin role screens are `/admin/users/`, `/admin/roles/`, and `/admin/orgs/`; the optional Django administration site is at `/django-admin/`.

Run checks and tests with:

```powershell
python manage.py check
python manage.py test
```

## Import the legacy MySQL data

The schema and two uploaded files were present in the Next.js project, but no database dump was included. The importer reads the old MySQL tables and copies referenced uploads into Django's private media directory. It preserves user IDs and roles; old SHA-256 password hashes are verified on the first sign-in and upgraded to Django's PBKDF2 format automatically.

Make the old MySQL database reachable, set `LEGACY_DATABASE_URL` in the shell without committing it, then run:

```powershell
$env:LEGACY_DATABASE_URL = 'mysql://USER:PASSWORD@HOST:3306/joes_trip'
python manage.py migrate
python manage.py import_legacy_mysql --upload-directory 'C:\Users\joemur\joes-trip-site\trip_2027_files'
Remove-Item Env:LEGACY_DATABASE_URL
```

Use the actual source connection privately; do not paste credentials into this README or commit them. The running Django site continues to use `db.sqlite3` after import. The `PyMySQL` dependency is only needed for the import command.

## Raspberry Pi OS and Apache2

These instructions target Raspberry Pi OS 64-bit with the distro Python and Apache `mod_wsgi` built for that same Python ABI. Install `mod_wsgi` from apt rather than pip:

```bash
sudo apt update
sudo apt install -y apache2 libapache2-mod-wsgi-py3 python3-venv python3-pip
sudo mkdir -p /srv/joes-trip-site
sudo chown "$USER":www-data /srv/joes-trip-site
```

Copy this project to `/srv/joes-trip-site`, then install the Python dependencies and initialize SQLite/static files:

```bash
cd /srv/joes-trip-site
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Create `/etc/joes-trip-site.env` outside the project, restrict its permissions, and set a unique `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS` to the Pi hostname/domain, and `CSRF_TRUSTED_ORIGINS` to the site's HTTPS origin. Django does not read `.env` automatically; expose those values to Apache through a systemd service environment override or suitable Apache environment configuration. Do not commit secrets.

The SQLite database and uploaded media must be writable by Apache; source code, virtualenv, and static assets only need to be readable. Keep the database directory writable so SQLite can create journal files:

```bash
sudo chgrp -R www-data /srv/joes-trip-site
sudo chmod -R g+rX /srv/joes-trip-site
sudo chmod g+w /srv/joes-trip-site /srv/joes-trip-site/db.sqlite3
sudo chmod -R g+rwX /srv/joes-trip-site/media
```

Edit `deploy/apache-joes-trip.conf` and replace `trip.example.com` with the real hostname. Then enable WSGI and the site:

```bash
sudo a2enmod wsgi
sudo cp deploy/apache-joes-trip.conf /etc/apache2/sites-available/joes-trip.conf
sudo a2ensite joes-trip.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Review `/var/log/apache2/joes-trip-error.log` for runtime errors. Configure DNS and HTTPS before exposing the site publicly. Back up both `db.sqlite3` and `media/`.
