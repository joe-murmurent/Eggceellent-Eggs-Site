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

Uploads are stored in the project's `media/` directory during local development (`DEBUG=True`). With `DEBUG=False`, uploads use `/mnt/seagate4tb` on the Raspberry Pi; uploaded trip files are placed in its `trip_2027_files/` subdirectory, organized into `images/`, `videos/`, and `other/`. The app chooses between these paths using `DEBUG`.

Event-form uploads use authenticated HTTP requests sent in 5 MiB chunks, so MP4 videos are not limited by a single large request. (Browsers cannot upload directly over SFTP.) An event can contain up to 8 files; total upload size is bounded by available storage rather than an application-level byte limit. Incomplete temporary chunks under `.upload_chunks` are removed after 24 hours when another chunk upload request runs.

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
sudo apt install -y apache2 libapache2-mod-wsgi-py3 python3-venv python3-pip certbot python3-certbot-apache
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

### Updating an existing deployment

After copying the updated project files to `/srv/joes-trip-site`, run the deployment script from that checkout:

```bash
cd /srv/joes-trip-site
bash deploy/update-site.sh
```

The script installs updated Python dependencies, applies database migrations, runs `collectstatic` on every deployment, validates the Apache configuration, and restarts Apache. Run it once after each code update; it is not part of Apache startup or normal web requests. The script expects the existing `.venv` and uses `sudo` for Apache validation and restart.

The SQLite database and mounted upload directory must be writable by Apache; source code, virtualenv, and static assets only need to be readable. Confirm `/mnt/seagate4tb` is mounted before starting Apache. Keep the database directory writable so SQLite can create journal files:

```bash
sudo chgrp -R www-data /srv/joes-trip-site
sudo chmod -R g+rX /srv/joes-trip-site
sudo chmod g+w /srv/joes-trip-site /srv/joes-trip-site/db.sqlite3
```

For an NTFS-3G upload drive, `chgrp` and `chmod` do not override the ownership/modes set at mount time. Check Apache's numeric group with `getent group www-data`, back up `/etc/fstab`, and set the `/mnt/seagate4tb` entry's `gid` to that group ID while retaining group-write masks (the current Pi uses `gid=33,dmask=007,fmask=117`). The NTFS mount applies that group and mode across the volume, so use a drive dedicated to site uploads rather than a shared drive containing data Apache must not access. After editing `/etc/fstab`, reload and remount it:

```bash
sudo cp -a /etc/fstab /etc/fstab.bak
sudoedit /etc/fstab
sudo systemctl daemon-reload
sudo systemctl stop apache2
sudo umount /mnt/seagate4tb
sudo mount /mnt/seagate4tb
sudo -u www-data test -w /mnt/seagate4tb/trip_2027_files
sudo systemctl start apache2
```

Production uses `FILE_UPLOAD_PERMISSIONS=None` so Django leaves file modes to NTFS-3G instead of attempting an unsupported `chmod` after each upload.

The production site is `https://murmurent.duckdns.org`, with `www.murmurent.duckdns.org` as an alias. Both names must resolve to the Pi, and inbound ports 80 and 443 must reach Apache. The Apache vhost uses a Let's Encrypt certificate managed by Certbot; it is not a self-signed certificate tied to the Pi's current IP.

For a first installation, obtain the certificate while Apache has an HTTP-only vhost. Create a temporary bootstrap vhost for the two names, enable it, and reload Apache before running Certbot:

```bash
sudo a2enmod wsgi rewrite
sudo tee /etc/apache2/sites-available/joes-trip-bootstrap.conf >/dev/null <<'EOF'
<VirtualHost *:80>
	ServerName murmurent.duckdns.org
	ServerAlias www.murmurent.duckdns.org
	DocumentRoot /var/www/html
</VirtualHost>
EOF
sudo a2ensite joes-trip-bootstrap.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
sudo certbot --apache --redirect -d murmurent.duckdns.org -d www.murmurent.duckdns.org
```

After Certbot has issued the certificate, install the production vhosts from this repository. The template redirects HTTP to HTTPS and references the Certbot-managed certificate paths:

```bash
sudo a2enmod ssl
sudo cp deploy/apache-joes-trip.conf /etc/apache2/sites-available/joes-trip.conf
sudo a2ensite joes-trip.conf
sudo a2dissite joes-trip-bootstrap.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Certbot handles renewal. The deploy hook validates Apache and reloads it only after the site's certificate is renewed. This Pi uses a daily 1 a.m. Pacific-time cron job; keep the systemd `certbot.timer` disabled if using this cron schedule:

```bash
sudo install -o root -g root -m 0755 deploy/setcert.py /etc/letsencrypt/renewal-hooks/deploy/joes-trip-apache-reload
sudo install -o root -g root -m 0644 deploy/joes-trip-setcert.cron /etc/cron.d/joes-trip-certbot
sudo certbot renew --dry-run
```

Check `/var/log/joes-trip-certbot.log` after the first scheduled run. Review `/var/log/apache2/joes-trip-error.log` and `/var/log/apache2/joes-trip-ssl-error.log` for runtime errors. Back up `db.sqlite3` and `/mnt/seagate4tb`.

Trip events can store coordinates as `latitude, longitude`; enter the coordinate pair shown when copying a location from any map provider. The trip journal uses MapLibre GL JS with OpenFreeMap's public Positron style to plot located events and connect them in event-date order. It requires no API key or Google account. Map tiles are served by OpenFreeMap, with map data from OpenStreetMap; attribution is shown on the map.

The admin-only Itinerary Planner can be populated from `2027_RV_Master_Trip_Planner.xlsx` in the project root by running `python manage.py import_itinerary_workbook`. The command imports stops, planning assumptions, and source links; repeated runs skip existing stops. Use `--update-existing` only when intentionally refreshing workbook fields; it preserves map coordinates entered in the planner.
