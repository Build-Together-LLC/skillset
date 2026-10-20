# Hosting recipes (reuse in any setup guide)

Copy these into a guide and change the names. Every command was run on Ubuntu 24.04.

## Which server for what

| Where the main app runs | Where a helper container (Docker) runs |
|---|---|
| Your laptop | Docker on the same laptop. Bind it to `127.0.0.1`. |
| Your own server or VPS | Same server (Docker + compose) or a second small VPS. |
| **Frappe Cloud** (managed ERPNext) | **A separate paid VPS.** Frappe Cloud runs only the Frappe stack, you cannot run Docker next to it. |

Paid server providers (any works, pick one near your users): [[DigitalOcean|https://www.digitalocean.com/pricing/droplets]],
[[Hetzner Cloud|https://www.hetzner.com/cloud]], [[AWS Lightsail|https://aws.amazon.com/lightsail/]],
[[Vultr|https://www.vultr.com/]], [[Linode (Akamai)|https://www.linode.com/]], [[Contabo|https://contabo.com/en/vps/]].
Sizing for a small helper container: 1 vCPU, 2 GB RAM, 40 GB SSD, Ubuntu 24.04 LTS, a public IPv4 address.

## Fresh Ubuntu server

```bash
adduser deploy && usermod -aG sudo deploy
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
apt update && apt install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx
usermod -aG docker deploy
```

## Where files live (show this as a tree diagram, type "tree")

```
/opt/<app>/                  compose project, owned by deploy
  docker-compose.yml         the stack
  .env                       secrets, chmod 600, never in Git
  sessions/ (or data/)       the container's state, back this up
/etc/nginx/sites-available/<app>        reverse proxy, symlinked into sites-enabled
/etc/letsencrypt/live/<domain>/         certificates (certbot renews them)
/var/backups/                nightly tar.gz of the state folder
```

## HTTPS in front of a container on 127.0.0.1:PORT

Stage 1: a plain `server { listen 80; server_name <domain>; }` file, `nginx -t && systemctl reload nginx`,
then `certbot --nginx -d <domain>`. Stage 2: replace the file with the full 80 -> 443 config that proxies
to `http://127.0.0.1:PORT`, add `allow <caller IP>; deny all;` in the 443 block, reload.

## Keep it alive and backed up

- Compose: `restart: unless-stopped`. Docker starts at boot.
- Backup cron: `0 2 * * * cd /opt/<app> && tar czf /var/backups/<app>-$(date +\%F).tar.gz sessions && find /var/backups -name '<app>-*.tar.gz' -mtime +7 -delete`
- Update: `docker compose pull && docker compose up -d`

## Frappe Cloud (managed ERP) specifics

Source: [[Custom app docs|https://docs.frappe.io/cloud/benches/custom-app]], [[Site config docs|https://docs.frappe.io/cloud/sites/site-config]].

- Custom apps need a **private bench group** (not a shared one).
- Dashboard: Bench group -> **Apps** -> **Add App** -> **Add from GitHub** -> authorise GitHub -> choose the
  repository and **branch** -> **Validate App** -> **Add App**. Then **Show updates** -> **Deploy**.
  After deploying, **update the site** so it installs the app and migrates.
- The app must have a valid `pyproject.toml` with `[tool.bench.frappe-dependencies]` naming the supported Frappe range.
- Site settings: site dashboard -> **Site Config** tab -> enter the value -> **Update Configuration**. Developer mode is
  not available, nothing you change on the server survives a deploy. So prefer settings stored in a **doctype**
  (a Single settings doctype with Password fields) over `site_config.json` or environment variables.
- You cannot run `bench` commands. Anything the guide tells a self-hosted user to run with `bench` becomes a
  dashboard action (install app, update site) or a button inside the app.
- The helper VPS must be reachable from Frappe Cloud over **HTTPS** and Frappe Cloud must be reachable from the
  VPS (the site URL, for webhooks). Frappe Cloud servers can change IP address, so an IP allow-list on the VPS can
  lock you out. Check the server's IP in the dashboard before using one, and rely on a hashed API key plus HTTPS
  otherwise.
