# AWS Deployment Guide — SQPAS

**Secure Multi-Party Question Paper Assembly and Controlled Release System**

This guide provides exact, safe instructions for deploying the SQPAS Flask application to an AWS EC2 instance (Ubuntu) using Gunicorn and Nginx.

---

## Command Location Legend

To prevent confusion, every step is marked with where the action should take place:

- ☁️ **AWS Console**: Actions performed in your web browser at `console.aws.amazon.com`.
- 💻 **Local Machine**: Commands run in your personal computer's terminal (Windows/Mac/Linux).
- 🖥️ **EC2 Server**: Commands run in the terminal *after* you have SSH'd into the Ubuntu server.

---

## Architecture Overview

```
┌──────────────┐      HTTPS       ┌──────────────┐      HTTP        ┌──────────────┐
│   Browser    │ ───────────────▶ │    Nginx     │ ──────────────▶ │  Gunicorn    │
│              │                  │  (port 80/   │   127.0.0.1    │  (port 8000) │
│              │                  │   443)       │                │  + Flask App │
└──────────────┘                  └──────────────┘                └──────┬───────┘
                                                                        │
                                                                        ▼
                                                                 ┌──────────────┐
                                                                 │ PostgreSQL   │
                                                                 │ RDS          │
                                                                 │ (port 5432)  │
                                                                 └──────────────┘
```

---

## Step 1: AWS Infrastructure Setup ☁️

1. **Log in**: ☁️ Open the **AWS Console**.
2. **EC2 Instance**: ☁️ Navigate to EC2 and launch an instance:
   - **Name**: `sqpas-server`
   - **OS**: Ubuntu 22.04 LTS
   - **Instance Type**: `t2.micro` or `t3.micro`
   - **Key Pair**: Create a new key pair (e.g., `sqpas-key.pem`). 💻 Download it to your local machine.
   - **Network**: Allow SSH traffic from "My IP", and allow HTTP/HTTPS traffic from anywhere.
3. **RDS Database**: ☁️ Navigate to RDS and create a database:
   - **Engine**: PostgreSQL 15 (Free Tier)
   - **Identifier**: `sqpas-db`
   - **Credentials**: Username `postgres`, auto-generate or set a strong password. Note this password securely!
   - **Public Access**: No.
   - **VPC Security Group**: Create new or use default, ensuring your EC2 instance's security group is allowed inbound access on port 5432.
   - **Initial Database Name**: Expand "Additional configuration" and set "Initial database name" to `sqpas_db`.

---

## Step 2: Connect to the EC2 Server 💻

1. 💻 Open a terminal on your local machine.
2. 💻 Restrict the permissions of your downloaded key file (Linux/Mac only):
   ```bash
   chmod 400 path/to/sqpas-key.pem
   ```
   *(On Windows, you may need to right-click the file -> Properties -> Security -> Advanced, disable inheritance, and remove all users except your current user).*
3. 💻 SSH into the EC2 instance using its Public IPv4 address:
   ```bash
   ssh -i path/to/sqpas-key.pem ubuntu@<EC2-PUBLIC-IP>
   ```

---

## Step 3: Install System Dependencies 🖥️

Run these commands on the Ubuntu server to prepare the environment.

1. 🖥️ Update system packages:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
2. 🖥️ Install Python, pip, virtual environment, Git, Nginx, and PostgreSQL client:
   ```bash
   sudo apt install -y python3 python3-pip python3-venv git nginx postgresql-client
   ```

---

## Step 4: Clone Repository and Setup Virtual Environment 🖥️

The application will reside in `/home/ubuntu/sqpas`.

1. 🖥️ Clone the GitHub repository:
   ```bash
   cd /home/ubuntu
   git clone <YOUR-GITHUB-REPO-URL> sqpas
   cd sqpas
   ```
2. 🖥️ Create and activate the virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. 🖥️ Install Python dependencies (including Gunicorn and psycopg2):
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## Step 5: Configure Production Environment 🖥️

1. 🖥️ Copy the `.env.example` file to create your `.env`:
   ```bash
   cp .env.example .env
   ```
2. 🖥️ Generate two secure 32-byte keys for Flask and Encryption:
   ```bash
   python -c "import secrets; print(f'SECRET_KEY={secrets.token_hex(32)}\nENCRYPTION_KEY={secrets.token_hex(32)}')"
   ```
3. 🖥️ Open the `.env` file using the `nano` editor:
   ```bash
   nano .env
   ```
4. 🖥️ Update the following variables in `.env`:
   - Paste the generated `SECRET_KEY` and `ENCRYPTION_KEY`.
   - Set `FLASK_ENV=production`
   - Set `BEHIND_PROXY=true`
   - Set the `DATABASE_URL` using your RDS endpoint and password from Step 1:
     `DATABASE_URL=postgresql://postgres:<RDS-PASSWORD>@<RDS-ENDPOINT>:5432/sqpas_db`
   - Save and exit (Press `Ctrl+O`, `Enter`, then `Ctrl+X`).
5. 🖥️ Secure the `.env` file so only the `ubuntu` user can read it:
   ```bash
   chmod 600 .env
   ```

---

## Step 6: Initialize and Seed the Database 🖥️

1. 🖥️ Ensure your virtual environment is active (`source venv/bin/activate` if not).
2. 🖥️ Run the seed script to create tables and demo users:
   ```bash
   python seed.py
   ```
   *Note: Save the demo credentials printed to the screen securely. Do not share them publicly.*

---

## Step 7: Test Gunicorn Locally 🖥️

1. 🖥️ Start the application using Gunicorn to verify it connects to the database and doesn't crash:
   ```bash
   gunicorn wsgi:app --config gunicorn.conf.py
   ```
2. 🖥️ Open a *second* terminal on your local machine, SSH into the EC2 instance again (Step 2), and test the local endpoint:
   ```bash
   curl -s http://127.0.0.1:8000/auth/login | grep "<title>"
   ```
   *You should see HTML output containing the SQPAS title. If successful, go back to the first terminal and stop Gunicorn with `Ctrl+C`.*

---

## Step 8: Configure Systemd Service 🖥️

To ensure the application runs in the background and restarts on reboot, we use `systemd`.

1. 🖥️ Copy the provided service file to systemd:
   ```bash
   sudo cp deploy/sqpas.service /etc/systemd/system/
   ```
2. 🖥️ Reload systemd, enable the service on boot, and start it:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable sqpas
   sudo systemctl start sqpas
   ```
3. 🖥️ Verify it is running:
   ```bash
   sudo systemctl status sqpas
   ```

---

## Step 9: Configure Nginx Reverse Proxy 🖥️

Nginx handles incoming HTTP/HTTPS traffic on port 80/443 and forwards it to Gunicorn on port 8000.

1. 🖥️ Copy the provided Nginx configuration:
   ```bash
   sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/sqpas
   ```
2. 🖥️ Enable the site and remove the default Nginx page:
   ```bash
   sudo ln -sf /etc/nginx/sites-available/sqpas /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   ```
3. 🖥️ Test the configuration for syntax errors:
   ```bash
   sudo nginx -t
   ```
4. 🖥️ Restart Nginx to apply changes:
   ```bash
   sudo systemctl restart nginx
   ```

---

## Step 10: Verification Checklist 💻

Open a browser on your local machine and navigate to `http://<EC2-PUBLIC-IP>`. Perform these checks:

- [ ] **Flask starts successfully**: You see the login page.
- [ ] **Nginx responds externally**: The URL is working via the public IP.
- [ ] **Admin login works**: Log in with `admin_demo` credentials.
- [ ] **MFA works**: Use the TOTP code (from your authenticator app) for the admin account.
- [ ] **Setter Isolation**: Log in as `setter_a` and verify you cannot access `/admin` or `/officer`.
- [ ] **Officer Isolation**: Log in as `officer_demo` and verify you cannot access `/admin/audit`.
- [ ] **Encrypted Section Workflow**: As a setter, submit a section. The database will encrypt it.
- [ ] **Approval and Release Workflow**: Admin can approve the section and assemble the paper. Officer can release it.
- [ ] **Audit logs are generated**: Log in as admin, go to the Audit Dashboard, and confirm login events are visible.
- [ ] **No secrets appear in logs**: Run `sudo journalctl -u sqpas -n 100` on the EC2 server and ensure passwords/keys are filtered.

---

## Maintenance Commands 🖥️

### Checking Logs
To view the live application logs (Gunicorn + Flask):
```bash
sudo journalctl -u sqpas -f
```

To view Nginx error logs:
```bash
sudo tail -f /var/log/nginx/error.log
```

### Applying Code Changes
If you push new code to GitHub and want to update the server:
```bash
cd /home/ubuntu/sqpas
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart sqpas
```

---

## Safe Teardown (For Demonstrations) ☁️

AWS charges by the hour. When your demonstration is complete, tear down the resources:

1. ☁️ **EC2 Dashboard**: Select `sqpas-server`, go to **Instance State**, and choose **Terminate instance**.
2. ☁️ **RDS Dashboard**: Select `sqpas-db`, go to **Actions**, and choose **Delete**. (Uncheck "Create final snapshot" to avoid storage costs).
3. ☁️ Ensure no Elastic IPs are left unattached in the EC2 dashboard.
