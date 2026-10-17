#!/usr/bin/env python3
"""Validate Apache and reload it after Certbot renews the site certificate."""

import os
import shutil
import subprocess


DOMAIN = "murmurent.duckdns.org"


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run this Certbot deploy hook as root.")

    renewed_domains = set(os.environ.get("RENEWED_DOMAINS", "").split())
    if DOMAIN not in renewed_domains:
        return

    apache2ctl = shutil.which("apache2ctl")
    systemctl = shutil.which("systemctl")
    if apache2ctl is None or systemctl is None:
        raise SystemExit("Could not find apache2ctl or systemctl in PATH.")

    subprocess.run([apache2ctl, "configtest"], check=True)
    subprocess.run([systemctl, "reload", "apache2"], check=True)


if __name__ == "__main__":
    main()