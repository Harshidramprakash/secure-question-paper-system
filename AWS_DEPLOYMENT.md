# AWS Deployment Guide — SQPAS

**Secure Multi-Party Question Paper Assembly and Controlled Release System**

This guide covers deploying SQPAS to AWS using EC2 + PostgreSQL RDS + Nginx.  
Each step is labeled **[DEMO REQUIRED]** or **[PRODUCTION HARDENING]**.

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

**AWS Services Used:**
| Service | Purpose | Required? |
|---------|---------|-----------|
| EC2 (Ubuntu 22.04) | Application server | ✅ Yes |
| RDS (PostgreSQL 15) | Production database | ✅ Yes |
| CloudWatch Logs | Log aggregation | 📌 Recommended |
| KMS | Encryption key management | 📌 Optional |
| Elastic IP | Static public IP | 📌 Recommended |

---

## Prerequisites

- AWS account (or college-provided AWS Academy account)
- Basic familiarity with SSH and Linux terminal
- The SQPAS GitHub repository URL

---

## Step 1: Create an AWS Account **[DEMO REQUIRED]**

1. Go to https://aws.amazon.com and create an account (or use the college-provided AWS Academy/Learner Lab account).
2. Sign in to the AWS Management Console.
3. Select a region close to your location (e.g., `ap-south-1` for Mumbai, India).

> ⚠️ **Cost Warning**: AWS resources incur charges. Always terminate resources when not in use. See Step 15 for cleanup instructions.

---

## Step 2: Create an EC2 Ubuntu Instance **[DEMO REQUIRED]**

1. Go to **EC2 → Launch Instance**.
2. Configure:
   - **Name**: `sqpas-server`
   - **AMI**: Ubuntu Server 22.04 LTS (64-bit, x86)
   - **Instance type**: `t2.micro` (free tier eligible) or `t3.small` for better performance
   - **Key pair**: Create a new key pair (download the `.pem` file — **keep it safe!**)
   - **Storage**: 20 GB gp3
3. Click **Launch Instance**.
4. Note the **Public IPv4 address** or allocate an **Elastic IP** (recommended).

---

## Step 3: Configure Security Group **[DEMO REQUIRED]**

Edit the security group attached to your EC2 instance:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | Your IP only | Remote access |
| HTTP | 80 | 0.0.0.0/0 | Web traffic |
| HTTPS | 443 | 0.0.0.0/0 | Encrypted web traffic |

**[PRODUCTION HARDENING]**: Remove SSH access from `0.0.0.0/0`. Use a bastion host or AWS Systems Manager Session Manager instead.

---

## Step 4: Install Dependencies **[DEMO REQUIRED]**

SSH into your EC2 instance:

```bash
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

Install required system packages:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python, pip, Git, Nginx, and PostgreSQL client
sudo apt install -y python3 python3-pip python3-venv git nginx postgresql-client

# Verify installations
python3 --version   # Should be 3.10+
git --version
nginx -v
```

---

## Step 5: Clone the Repository **[DEMO REQUIRED]**

```bash
# Clone the project
cd /home/ubuntu
git clone <YOUR-GITHUB-REPO-URL> sqpas
cd sqpas
```

---

## Step 6: Create Virtual Environment **[DEMO REQUIRED]**

```bash
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 7: Install Python Requirements **[DEMO REQUIRED]**

Already covered in Step 6. Verify key packages:

```bash
pip list | grep -E "Flask|SQLAlchemy|gunicorn|psycopg2|cryptography"
```

Expected output:
```
Flask                 3.x.x
Flask-Login           0.6.x
Flask-SQLAlchemy      3.x.x
Flask-WTF             1.x.x
gunicorn              22.x.x
psycopg2-binary       2.9.x
cryptography          43.x.x
```

---

## Step 8: Configure Environment Variables **[DEMO REQUIRED]**

Create the production `.env` file:

```bash
cd /home/ubuntu/sqpas

# Copy the template
cp .env.example .env

# Generate secure keys
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo "Generated SECRET_KEY:     $SECRET_KEY"
echo "Generated ENCRYPTION_KEY: $ENCRYPTION_KEY"
echo ""
echo "⚠️  SAVE THESE KEYS SECURELY. Losing the ENCRYPTION_KEY means"
echo "   all encrypted question papers are UNRECOVERABLE."
```

Edit `.env` with the generated values:

```bash
nano .env
```

Set these values:
```ini
FLASK_ENV=production
SECRET_KEY=<paste-generated-secret-key>
ENCRYPTION_KEY=<paste-generated-encryption-key>
DATABASE_URL=postgresql://sqpas_user:<RDS-PASSWORD>@<RDS-ENDPOINT>:5432/sqpas_db
LOG_LEVEL=INFO
BEHIND_PROXY=true
```

Secure the file:
```bash
chmod 600 .env
```

**[PRODUCTION HARDENING]**: Use AWS Secrets Manager or Parameter Store instead of a `.env` file.

---

## Step 9: Create and Configure PostgreSQL RDS **[DEMO REQUIRED]**

### 9a. Create the RDS Instance

1. Go to **RDS → Create Database**.
2. Configure:
   - **Engine**: PostgreSQL 15
   - **Template**: Free tier (for demo) or Production
   - **DB Instance Identifier**: `sqpas-db`
   - **Master username**: `sqpas_admin`
   - **Master password**: Generate a strong password
   - **Instance class**: `db.t3.micro` (free tier) or `db.t3.small`
   - **Storage**: 20 GB gp3
   - **VPC**: Same VPC as your EC2 instance
   - **Public access**: No (only accessible from within the VPC)
3. Under **Additional configuration**:
   - **Initial database name**: `sqpas_db`
4. Click **Create database** and wait for it to become available.

### 9b. Configure Security Group for RDS

Create or modify the RDS security group:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| PostgreSQL | 5432 | EC2 Security Group | App → DB access |

### 9c. Test Connection from EC2

```bash
psql -h <RDS-ENDPOINT> -U sqpas_admin -d sqpas_db
# Enter the password when prompted
# Type \q to exit
```

### 9d. Create Application User (Optional but Recommended)

```sql
-- Connect as sqpas_admin, then:
CREATE USER sqpas_user WITH PASSWORD 'STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON DATABASE sqpas_db TO sqpas_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sqpas_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sqpas_user;
\q
```

Update `DATABASE_URL` in `.env`:
```
DATABASE_URL=postgresql://sqpas_user:STRONG_PASSWORD_HERE@<RDS-ENDPOINT>:5432/sqpas_db
```

---

## Step 10: Initialize the Database **[DEMO REQUIRED]**

```bash
cd /home/ubuntu/sqpas
source venv/bin/activate

# The Flask app creates tables automatically on first run.
# To seed demo users:
python seed.py

# Verify tables were created:
FLASK_ENV=production python -c "
from app import create_app
from app.extensions import db
app = create_app()
with app.app_context():
    tables = db.engine.table_names() if hasattr(db.engine, 'table_names') else list(db.metadata.tables.keys())
    print('Tables:', tables)
"
```

> **Note**: `seed.py` creates demo users with pre-set passwords. For production, change all passwords and rotate MFA secrets after the initial demo.

---

## Step 11: Start the Application with Gunicorn **[DEMO REQUIRED]**

### Quick Test

```bash
cd /home/ubuntu/sqpas
source venv/bin/activate
gunicorn wsgi:app --config gunicorn.conf.py
```

Verify: `curl http://127.0.0.1:8000/auth/login` should return HTML.

### Set Up as a systemd Service

```bash
# Copy the service file
sudo cp deploy/sqpas.service /etc/systemd/system/sqpas.service

# Adjust paths if needed
sudo nano /etc/systemd/system/sqpas.service

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable sqpas
sudo systemctl start sqpas

# Check status
sudo systemctl status sqpas

# View logs
sudo journalctl -u sqpas -f
```

---

## Step 12: Configure Nginx as Reverse Proxy **[DEMO REQUIRED]**

```bash
# Copy the example Nginx config
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/sqpas

# Edit the server_name if you have a domain
sudo nano /etc/nginx/sites-available/sqpas

# Enable the site
sudo ln -sf /etc/nginx/sites-available/sqpas /etc/nginx/sites-enabled/sqpas
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

Verify: Open `http://<EC2-PUBLIC-IP>` in your browser. You should see the SQPAS login page.

**[PRODUCTION HARDENING]**: Configure SSL/TLS with Let's Encrypt:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## Step 13: Configure CloudWatch Logging **[PRODUCTION HARDENING]**

### 13a. Install the CloudWatch Agent

```bash
# Download and install
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Copy the config
sudo cp deploy/cloudwatch-agent-config.json /opt/aws/amazon-cloudwatch-agent/etc/

# Start the agent
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent-config.json
```

### 13b. IAM Role for CloudWatch

Attach the `CloudWatchAgentServerPolicy` managed policy to the EC2 instance's IAM role.

---

## Step 14: Test the Deployed Application **[DEMO REQUIRED]**

### Basic Health Check

```bash
# From EC2 instance
curl -s http://127.0.0.1:8000/auth/login | head -20

# From your browser
# Navigate to http://<EC2-PUBLIC-IP>/
```

### Functional Testing

1. **Login**: Use the demo credentials from `seed.py` output.
2. **Create Paper**: Log in as admin → Create a question paper.
3. **Submit Sections**: Log in as setter_a and setter_b → Submit sections.
4. **Review & Approve**: Log in as admin → Approve sections → Assemble paper.
5. **Release**: Log in as officer → Release the paper when time has passed.
6. **Audit Logs**: Log in as admin → View audit dashboard.

### Security Header Check

```bash
curl -I http://<EC2-PUBLIC-IP>/auth/login
# Should see:
#   X-Content-Type-Options: nosniff
#   X-Frame-Options: SAMEORIGIN
#   Referrer-Policy: strict-origin-when-cross-origin
#   Content-Security-Policy: ...
```

---

## Step 15: Cleanup — Avoid Unnecessary Charges **[DEMO REQUIRED]**

> ⚠️ **IMPORTANT**: AWS charges by the hour. Always clean up after your demo.

```bash
# 1. Stop the application
sudo systemctl stop sqpas

# 2. Stop Nginx
sudo systemctl stop nginx
```

**In the AWS Console:**

1. **EC2**: Select your instance → Instance State → **Stop Instance** (to pause) or **Terminate Instance** (to delete permanently).
2. **RDS**: Select your database → Actions → **Stop** (temporary) or **Delete** (permanent). Uncheck "Create final snapshot" for demo databases.
3. **Elastic IP**: Release any allocated Elastic IPs (they charge when not attached to a running instance).
4. **Security Groups**: Can be left (no charge) or deleted.

---

## Production Hardening Checklist

These items are **not required for the college demo** but should be addressed before any real deployment:

| Item | Status | Priority |
|------|--------|----------|
| SSL/TLS with Let's Encrypt or ACM | ⬜ | 🔴 Critical |
| Change all demo user passwords | ⬜ | 🔴 Critical |
| Rotate all MFA secrets | ⬜ | 🔴 Critical |
| Use AWS Secrets Manager for credentials | ⬜ | 🟡 High |
| Enable KMS envelope encryption | ⬜ | 🟡 High |
| Set up automated backups for RDS | ⬜ | 🟡 High |
| Enable RDS encryption at rest | ⬜ | 🟡 High |
| Configure VPC with private subnets | ⬜ | 🟡 High |
| Set up WAF (Web Application Firewall) | ⬜ | 🟢 Medium |
| Enable CloudTrail for AWS API auditing | ⬜ | 🟢 Medium |
| Set up monitoring alarms (CloudWatch) | ⬜ | 🟢 Medium |
| Use a load balancer (ALB) | ⬜ | 🟢 Medium |
| Implement rate limiting | ⬜ | 🟢 Medium |
| Regular security patching schedule | ⬜ | 🟡 High |

---

## Troubleshooting

### Application won't start
```bash
# Check logs
sudo journalctl -u sqpas -n 50
# Check .env file permissions
ls -la /home/ubuntu/sqpas/.env
# Test config
cd /home/ubuntu/sqpas && source venv/bin/activate
python -c "from app import create_app; app = create_app(); print('OK')"
```

### Can't connect to RDS
```bash
# Test connectivity
nc -zv <RDS-ENDPOINT> 5432
# Check security group allows EC2 → RDS
# Check DATABASE_URL in .env
```

### Nginx shows 502 Bad Gateway
```bash
# Check if Gunicorn is running
sudo systemctl status sqpas
# Check Gunicorn is bound to 127.0.0.1:8000
ss -tlnp | grep 8000
# Check Nginx error log
sudo tail -20 /var/log/nginx/error.log
```

### Static files not loading
```bash
# Nginx serves static files directly — check the alias path
sudo nginx -t
ls /home/ubuntu/sqpas/app/static/
```
