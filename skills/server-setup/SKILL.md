---
name: server-setup
description: "..."
---

<!-- hidden: Automated setup of a new VPS server — SSH keys, security, firewall, fail2ban, Docker. -->

# New VPS Server Setup

Help the user fully configure a fresh VPS server: from creating SSH keys to installing Docker. The entire process is step-by-step, with checks at each stage.

## What to ask the user before starting

If not specified — ask:
- **Server IP address** (required)
- **Username to create** (default: `coolify`)
- **Timezone** (default: `Europe/Moscow`)

## Critical security rules

These rules exist to prevent losing access to the server:

- **NEVER** disable root access and password authentication without first verifying login via the new user
- **ALWAYS** run `sshd -t` before `systemctl restart ssh`
- **ALWAYS** verify server accessibility immediately after restarting SSH
- When connecting via SSH, use `-o IdentitiesOnly=yes` to avoid "Too many authentication failures" errors
- Order is mandatory: create user → verify login → modify SSH config → verify again

---

## Step 1: SSH keys on the local machine

Check if the key `~/.ssh/id_ed25519_vps` exists:

```bash
ls -la ~/.ssh/id_ed25519_vps* 2>/dev/null && echo "EXIST" || echo "NOTEXIST"
```

If no keys exist — create them (using a unique name to avoid overwriting existing keys):

```bash
ssh-keygen -t ed25519 -C "vps-server-key" -f ~/.ssh/id_ed25519_vps -N ""
```

After creation, show the public key:
```bash
cat ~/.ssh/id_ed25519_vps.pub
```

---

## Step 2: Copy key to server (MANUAL STEP)

This is the only step that requires manual password entry. Tell the user:

> Run this command in the terminal and enter the root password:
> ```bash
> ssh-copy-id -i ~/.ssh/id_ed25519_vps.pub root@SERVER_IP
> ```
> Let me know when done.

Wait for user confirmation. Verify the connection:

```bash
ssh -i ~/.ssh/id_ed25519_vps -o IdentitiesOnly=yes -o ConnectTimeout=10 root@SERVER_IP "echo OK"
```

Proceed only if the command returned `OK`.

---

## Step 3: System update and package installation

Execute via SSH (`ssh -i ~/.ssh/id_ed25519_vps -o IdentitiesOnly=yes root@SERVER_IP`):

```bash
apt update && apt upgrade -y && apt install -y \
  curl wget git vim htop ufw fail2ban \
  unattended-upgrades apt-transport-https \
  ca-certificates software-properties-common
```

---

## Step 4: Create user

```bash
USERNAME="coolify"  # replace as needed

adduser $USERNAME --gecos "" --disabled-password
echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" | tee /etc/sudoers.d/$USERNAME

# Copy SSH key for the new user
mkdir -p /home/$USERNAME/.ssh
chmod 700 /home/$USERNAME/.ssh
cp /root/.ssh/authorized_keys /home/$USERNAME/.ssh/authorized_keys
chmod 600 /home/$USERNAME/.ssh/authorized_keys
chown -R $USERNAME:$USERNAME /home/$USERNAME/.ssh
```

---

## Step 4.3: CRITICAL CHECK — login as the new user

**MANDATORY** before modifying SSH config. Run LOCALLY:

```bash
ssh -i ~/.ssh/id_ed25519_vps -o IdentitiesOnly=yes -o ConnectTimeout=10 USERNAME@SERVER_IP "whoami && sudo whoami"
```

**Expected result:** two lines — `coolify` and `root`.

If the result is NOT as expected — troubleshoot the issue, do NOT proceed to step 4.4.

---

## Step 4.4: SSH security configuration

Only after successful check in 4.3:

```bash
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

tee /etc/ssh/sshd_config.d/99-custom.conf > /dev/null <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 6
ClientAliveInterval 300
ClientAliveCountMax 2
EOF

# Validate config
sshd -t && echo "Config is valid" || echo "ERROR — do not restart!"

# Restart only if validation passed
sshd -t && systemctl restart ssh && echo "SSH restarted"
```

**Immediately verify** that the server is still accessible (run LOCALLY):

```bash
ssh -i ~/.ssh/id_ed25519_vps -o IdentitiesOnly=yes -o ConnectTimeout=10 USERNAME@SERVER_IP "echo SSH is working"
```

If the connection is lost — this is a critical issue, the user needs KVM access from the hosting provider.

---

## Step 5: Firewall (UFW)

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose
```

---

## Step 6: Fail2Ban

```bash
cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

tee /etc/fail2ban/jail.local > /dev/null <<'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400
EOF

systemctl enable fail2ban
systemctl restart fail2ban
```

---

## Step 7: Automatic security updates

```bash
apt install -y unattended-upgrades
dpkg-reconfigure --priority=low unattended-upgrades
systemctl status unattended-upgrades --no-pager
```

---

## Step 8: Timezone and locale

```bash
timedatectl set-timezone Europe/Moscow
locale-gen ru_RU.UTF-8
update-locale LANG=ru_RU.UTF-8
```

---

## Step 9: Docker

```bash
apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

usermod -aG docker $USERNAME
systemctl enable docker
systemctl start docker

docker --version
docker compose version
```

After being added to the docker group, the user needs to re-login.

---

## Step 10: Final verification

Tell the user to open a new terminal and connect as the new user. Then run the verification checklist via SSH:

```bash
whoami
sudo whoami
sudo ufw status
sudo fail2ban-client status
docker --version
docker compose version
sudo systemctl status unattended-upgrades --no-pager
id
```

Show the results to the user and confirm successful setup.

---

## Optional: Change SSH port

If the user wants additional protection:

```bash
# Add to /etc/ssh/sshd_config.d/99-custom.conf:
# Port 2222

sudo ufw allow 2222/tcp
sudo ufw delete allow 22/tcp
sudo systemctl restart sshd
```
