
# Raspberry Pi: mDNS + Flask **filebox** + Nginx subdomains + Dynamic mDNS

> **Target setup (Raspberry Pi / Debian 12 Bookworm)**  
> - `wlan1` = **station** on your home LAN (e.g., `192.168.1.x`).  
> - `wlan0` = **hotspot/AP** managed by NetworkManager (e.g., `192.168.4.1`).  
> - NetworkManager’s **nm‑dnsmasq** serves DHCP/DNS for the hotspot on `wlan0`.  
> - Goal: make `filebox.brains.local` (and optional subdomains) accessible across **LAN (`wlan1`) via mDNS**; hotspot publication optional.

---

## Contents

1. [Prerequisites](#0-prerequisites)  
2. [Enable mDNS (Avahi + NSS)](#1-enable-mdns-avahi--nss)  
3. [Flask **filebox** + Gunicorn + systemd](#2-create--run-the-flask-web-app-filebox-with-gunicorn--systemd)  
4. [Nginx reverse proxy + subdomains](#3-nginx-reverse-proxy--subdomains)  
5. [Dynamic mDNS on `wlan1` (LAN); optional `wlan0` hotspot](#4-dynamic-mdns-aliases-on-wlan1-lan--plus-hotspot-optional)  
6. [Security & Credentials Management (filebox)](#5-security--credentials-management-filebox)  
7. [End‑to‑end tests](#6-end-to-end-tests)  
8. [Troubleshooting](#7-troubleshooting-tips)  
9. [Appendix: Advertise HTTP via DNS‑SD](#appendix-advertise-http-service-via-dns-sd)  
10. [References](#references)

---

## 0. Prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx
```

Verify interfaces and NM status:

```bash
nmcli dev status
ip addr show wlan1
ip addr show wlan0
```

---

## 1) Enable mDNS (Avahi + NSS)

Install **Avahi** (mDNS/DNS‑SD responder) + **libnss‑mdns** and update **NSS** so `.local` queries resolve via mDNS first. citeturn10search79

```bash
sudo apt install -y avahi-daemon avahi-utils libnss-mdns

# Backup and update NSS config
sudo cp /etc/nsswitch.conf /etc/nsswitch.conf.bak
sudo sed -i -E 's/^hosts:.*/hosts:          files mdns4_minimal [NOTFOUND=return] dns/' /etc/nsswitch.conf

# Enable + start Avahi
sudo systemctl enable --now avahi-daemon
```

> Allow **UDP 5353** multicast on your AP/firewall; Debian’s Avahi guide highlights this requirement for mDNS. citeturn10search79

**Quick checks:**

```bash
avahi-browse --all --ignore-local --resolve --terminate
avahi-resolve -n "$(hostname).local"
```

Avahi provides mDNS/DNS‑SD; `avahi-utils` includes `avahi-resolve`, `avahi-browse`. citeturn10search83

---

## 2) Create & run the Flask web app (**filebox**) with Gunicorn + systemd

We’ll deploy Flask behind **Gunicorn** (production WSGI) and manage it with **systemd**. Gunicorn is preferred over the Flask dev server for production. citeturn10search98

### 2.1 Project skeleton & virtualenv

```bash
# Project directory
mkdir -p ~/filebox && cd ~/filebox
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install flask gunicorn
```

### 2.2 Minimal Flask app

Create `app.py`:

```python
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello from filebox!'

@app.route('/healthz')
def healthz():
    return 'ok'
```

> Tutorial references show moving from the Flask dev server to **Gunicorn** for production workloads. citeturn10search98

### 2.3 Manual Gunicorn test

```bash
gunicorn --bind 127.0.0.1:8000 --workers 2 app:app
# In another terminal
curl -sS http://127.0.0.1:8000/ ; echo
curl -sS http://127.0.0.1:8000/healthz ; echo
```

### 2.4 systemd unit for Gunicorn

Create `/etc/systemd/system/filebox.service`:

```ini
[Unit]
Description=Gunicorn for Flask filebox
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/filebox
Environment="PATH=/home/pi/filebox/.venv/bin"
ExecStart=/home/pi/filebox/.venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 2 app:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable & start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now filebox.service
systemctl status filebox.service --no-pager
```

**Smoke test:**

```bash
curl -sS http://127.0.0.1:8000/ ; echo
```

---

## 3) Nginx reverse proxy + subdomains

Put **Nginx** in front of Gunicorn. Use `proxy_pass` to forward HTTP to `127.0.0.1:8000`. citeturn10search91

### 3.1 Server block for `filebox.brains.local`

Create `/etc/nginx/sites-available/filebox.conf`:

```nginx
server {
    listen 80;
    server_name filebox.brains.local;

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8000;
    }
}
```

Link, test, reload:

```bash
sudo ln -s /etc/nginx/sites-available/filebox.conf /etc/nginx/sites-enabled/filebox.conf
sudo nginx -t
sudo systemctl reload nginx
```

Nginx’s reverse proxy docs cover `proxy_pass`, forwarded headers, and upstream behavior. citeturn10search91

### 3.2 Optional: wildcard subdomains

You can add more subdomains with additional `server` blocks (e.g., `api.brains.local`), or use a wildcard:

```nginx
server {
    listen 80;
    server_name *.brains.local;
    location / { proxy_pass http://127.0.0.1:8000; }
}
```

See Nginx documentation on **server names** and virtual hosting. citeturn10search92

**Local proxy test:**

```bash
curl -H 'Host: filebox.brains.local' http://127.0.0.1/
```

---

## 4) Dynamic mDNS aliases on `wlan1` (LAN) — plus hotspot (optional)

Your **Dynamic mDNS installer (v2)** creates:
- `avahi-alias@.service` with `ExecStart=/usr/local/sbin/avahi-alias-publish %I` to publish aliases that follow the current interface IP.  
- A NetworkManager **dispatcher** script that restarts aliases on `up`/`dhcp4-change`. Docs describe dispatcher script locations, arguments, and actions. citeturn10search85  
- Optional DNS‑SD `_http._tcp` service under `/etc/avahi/services/`.

### 4.1 Publish the LAN alias (wlan1)

```bash
# Publish filebox.brains.local bound to wlan1 and advertise HTTP:80
sudo ./install_dynamic_mdns_v2.sh --alias filebox.brains.local --iface wlan1 --advertise-http --http-port 80

# Check status
systemctl status avahi-alias@filebox.brains.local.service --no-pager
```

The installer uses `avahi-publish -a -R` to register an address/hostname mapping and avoid reverse PTR collisions, enabling multiple aliases to the same IP. citeturn4search31

**Verify from LAN clients (`wlan1` network):**

```bash
# macOS/iOS (Bonjour):
ping filebox.brains.local

# Linux clients:
avahi-resolve -n filebox.brains.local
getent hosts filebox.brains.local
```

Debian’s Avahi wiki outlines `.local` mDNS behavior when using NSS; Avahi’s project site explains mDNS/DNS‑SD. citeturn10search79turn10search83

### 4.2 Optional: publish the alias for the hotspot (`wlan0`)

#### A) Avahi (mDNS) on `wlan0` — exact command
If you want **mDNS** (Bonjour) on the hotspot as well, publish the alias bound to `wlan0`:
```bash
# Publish filebox.brains.local for the hotspot IP (typically 192.168.4.1)
sudo ./install_dynamic_mdns_v2.sh --alias filebox.brains.local --iface wlan0 --advertise-http --http-port 80

# Verify the alias unit
systemctl status avahi-alias@filebox.brains.local.service --no-pager

# Confirm Avahi sees wlan0
journalctl -u avahi-daemon -n 50 --no-pager | grep -E 'wlan0|New relevant interface'
```
> Reminder: `.local` is reserved for **mDNS**; it is intended to be resolved via multicast, not traditional unicast DNS. Keep this in mind to avoid conflicts with upstream DNS. citeturn10search79

#### B) nm‑dnsmasq (unicast DNS) on the hotspot — wildcard mapping
If you prefer **regular DNS** on the hotspot (for clients that don’t do mDNS), add a mapping for the whole `brains.local` zone to the AP address:
```bash
sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d
echo "address=/brains.local/192.168.4.1" | sudo tee /etc/NetworkManager/dnsmasq-shared.d/brains-local.conf

# Bounce the Hotspot so the embedded dnsmasq picks up the file
nmcli connection down Hotspot
nmcli connection up Hotspot
```
- NetworkManager’s hotspot (shared mode) starts its own **dnsmasq** and, on modern builds, passes a `--conf-dir=/etc/NetworkManager/dnsmasq-shared.d` argument; using that directory is the intended way to add local records. citeturn2search30  
- The `address=/brains.local/192.168.4.1` line makes **both `brains.local` and any subdomain** (e.g., `filebox.brains.local`, `api.brains.local`) resolve to the AP IP **for hotspot clients only**.

> ⚠️ **Caution:** Because `.local` is reserved for mDNS, answering `.local` via **unicast DNS** can lead to odd behavior in some environments. Use this nm‑dnsmasq mapping only on the hotspot network, and prefer Avahi/mDNS for `.local` where possible. citeturn10search79

#### C) Optional: confirm Hotspot mode and IP
Make sure the Hotspot is in **shared** mode and that `wlan0` has the intended IP (NetworkManager defaults to a `10.42.x.x` range when sharing; your setup uses `192.168.4.1`):
```bash
nmcli connection show Hotspot | sed -n '1,120p'
ip addr show wlan0 | grep 'inet '
```
If you need to control the hotspot subnet/gateway precisely, set the connection to `method=shared` and specify `address1=` inside `/etc/NetworkManager/system-connections/Hotspot` (or your actual connection name). See examples for assigning a specific range to a specific interface in NM Hotspot setups. citeturn2search29

> Note: the connection name **Hotspot** may differ on your system; run `nmcli connection show` to identify it.

#### D) Tests from a hotspot client
After connecting a device to the AP:
```bash
# If you published mDNS via Avahi on wlan0
ping filebox.brains.local

# If you used nm-dnsmasq mapping
nslookup filebox.brains.local   # or: getent hosts filebox.brains.local
curl -sS http://filebox.brains.local/ ; echo
```

---

## 5) Security & Credentials Management (filebox)

> This section merges and refines your **User Authentication Credentials Management Guide** for the **filebox** app.

### 5.1 Security recommendations

1. **Change default admin password**
   ```python
   # Generate new password hash
   from werkzeug.security import generate_password_hash
   username = "user1"
   new_password = "my_super_strong_password"
   password_hash = generate_password_hash(new_password)
   print(f"{username}:{password_hash}")
   ```

2. **Update credentials file**
   ```text
   # user_credentials.txt
   admin:pbkdf2:sha256:600000$N0yVr0Fd$f7a9d...e8c
   ```

3. **Password requirements**
   - Minimum 12 characters  
   - Mix of uppercase, lowercase, numbers, and symbols  
   - Avoid common words or patterns

4. **Regular rotation**
   - Change passwords every 90 days  
   - Update the credentials file immediately

### 5.2 File management best practices

1. **Set proper file permissions**
   ```bash
   chmod 600 user_credentials.txt
   chown root:root user_credentials.txt
   ```

2. **Secure storage location**
   ```python
   # In app.py
   app.config['USER_CREDENTIALS_FILE'] = '/etc/app_credentials/user_credentials.txt'
   ```

3. **Backup strategy**
   ```bash
   # Backup with timestamp
   cp user_credentials.txt /secure/backup/location/$(date +%F)-credentials.txt
   # Encrypt before storing
   gpg --encrypt --recipient admin@example.com user_credentials.txt
   ```

4. **Add new users**
   ```python
   from werkzeug.security import generate_password_hash
   username = "newuser"
   password = "secure_password123!"
   password_hash = generate_password_hash(password)
   print(f"{username}:{password_hash}")  # Append to credentials file
   ```

5. **Disable default user**
   ```text
   # Comment the default user once replaced
   # admin:pbkdf2:sha256:600000$N0yVr0Fd$f7a9d...e8c
   ```

> **Important:** Store the credentials file **outside** the web root and restrict access to privileged users.

### 5.3 Error handling procedures

1. **Missing credentials file**
   - App creates a new file with default admin user  
   - Generates secure random password  
   - Logs credentials to application logs

2. **Invalid file entries**
   ```text
   # Examples of corrupted lines:
   admin:invalid_hash_format
   :empty_username
   missing_colon
   ```
   - Skip malformed lines during login  
   - Log warning: `Skipped invalid credential line: N`

3. **File access errors**
   - Log the error and return HTTP 500 on login attempts  
   - Preserve existing sessions

4. **Empty credentials file**
   - Treat as missing; recreate with default admin user  
   - Log warning: `Credentials file empty, regenerating`

5. **Audit trail (log snippets)**
   ```log
   WARNING: Created default user: admin with password: X7gFk93jLnQ2
   ERROR: [Errno 13] Permission denied: 'user_credentials.txt'
   WARNING: Skipped invalid credential line: 5
   ```

### 5.4 Quick reference (commands)

- Generate hash (Python REPL):
  ```python
  from werkzeug.security import generate_password_hash
  generate_password_hash('password')
  ```
- Tighten file perms:
  ```bash
  chmod 600 user_credentials.txt
  ```
- Add new user inline:
  ```bash
  echo "user:$(python -c 'from werkzeug.security import generate_password_hash; print(generate_password_hash("password"))')" >> user_credentials.txt
  ```
- Verify lines roughly:
  ```bash
  grep -vE '^(#|$)' user_credentials.txt | awk -F: '{print NF-1}' | grep -v 1
  ```

---

## 6) End‑to‑end tests

### 6.1 From a LAN client (`wlan1` network)

```bash
# Name resolution via mDNS
avahi-resolve -n filebox.brains.local

# HTTP via Nginx
curl -sS http://filebox.brains.local/ ; echo
curl -sS http://filebox.brains.local/healthz ; echo
```

### 6.2 From a hotspot client (optional)

```bash
# If alias is published on wlan0 via Avahi or nm-dnsmasq
ping filebox.brains.local
curl -sS http://filebox.brains.local/ ; echo
```

### 6.3 Server‑side quick checks

```bash
# Interfaces
nmcli dev status
ip addr show wlan1 ; ip addr show wlan0

# Nginx
sudo nginx -t
sudo systemctl status nginx --no-pager

# Gunicorn (Flask)
systemctl status filebox.service --no-pager
journalctl -u filebox.service -n 50 --no-pager

# Avahi + alias unit
systemctl status avahi-daemon --no-pager
systemctl status avahi-alias@filebox.brains.local.service --no-pager
journalctl -u avahi-alias@filebox.brains.local.service -n 50 --no-pager

# Dispatcher
ls -la /etc/NetworkManager/dispatcher.d/
```

The `--no-pager` option disables paging in `systemctl`/`journalctl` so output prints directly to the terminal. citeturn7search56turn7search70

---

## 7) Troubleshooting tips

- **mDNS not resolving**: Confirm **UDP 5353** multicast is allowed on AP/firewall; ensure `/etc/nsswitch.conf` has `mdns4_minimal [NOTFOUND=return]`. citeturn10search79  
- **Dispatcher not firing**: `NetworkManager-dispatcher.service` must be enabled; scripts must be root‑owned and executable under `/etc/NetworkManager/dispatcher.d/`. citeturn10search85  
- **Nginx**: `sudo nginx -t` then `sudo systemctl reload nginx`; see reverse proxy docs for tuning headers and buffering. citeturn10search91  
- **Gunicorn scaling**: Increase `--workers` (CPU cores × 2 or more); confirm the service `Environment` points to your venv. (General Gunicorn/Flask deployment practices.) citeturn10search98  
- **Validate unit files**: `sudo systemd-analyze verify /etc/systemd/system/<unit>.service` to pinpoint parsing errors. citeturn7search62

---

## Appendix: Advertise HTTP service via DNS‑SD

Avahi can publish `_http._tcp` so Bonjour browsers discover the service:

```xml
# /etc/avahi/services/filebox-http.service
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">%h filebox</name>
  <service>
    <type>_http._tcp</type>
    <port>80</port>
    <host-name>filebox.brains.local</host-name>
  </service>
</service-group>
```

Reload Avahi:

```bash
sudo systemctl reload avahi-daemon
```

Avahi service definitions under `/etc/avahi/services/` are automatically loaded. citeturn10search83

---

## References

- **Debian Avahi wiki** — mDNS/NSS `.local` behavior and recommended `hosts:` line. citeturn10search79  
- **Avahi (project site)** — mDNS/DNS‑SD overview & utilities. citeturn10search83  
- **`avahi-publish` man** — address mapping and `-R` to avoid reverse PTR collisions. citeturn4search31  
- **NetworkManager dispatcher** — scripts, actions (`up`, `down`, `dhcp4-change`). citeturn10search85  
- **Nginx reverse proxy docs** — `proxy_pass`, forwarded headers. citeturn10search91  
- **Nginx server names** — virtual hosting/wildcards. citeturn10search92  
- **Flask + Gunicorn deployment** — why Gunicorn vs. dev server; systemd pattern. citeturn10search98  
- **Systemd unit verification** — `systemd-analyze verify`. citeturn7search62  
- **systemctl / journalctl `--no-pager`** — man pages for options. citeturn7search56turn7search70
