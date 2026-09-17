# Secure Multi-Party Question Paper Assembly System (SQPAS)

This is the SQPAS Flask application. It implements role-based access control, AES-256-GCM encryption, secure multi-party assembly, and controlled release of examination papers.

## Features

- **Role-Based Access Control**: Admin, Setter (A/B), and Officer roles.
- **MFA / TOTP**: Multi-factor authentication required for all users.
- **Secure Encrypted Sections**: AES-256-GCM envelope encryption using AWS KMS (or local key) to secure section data at rest.
- **Controlled Release**: Question papers remain inaccessible until a strict scheduled release time.
- **Audit Dashboard**: Immutable logging of all sensitive access and actions.

## Quickstart

1. **Install dependencies**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Database Setup (Neon PostgreSQL)**:
   This application strictly requires a PostgreSQL database.
   - Create a free database on [Neon](https://neon.tech).
   - Get the connection string (it will look like `postgresql://USER:PASSWORD@HOST/DB?sslmode=require&channel_binding=require`).

3. **Configure environment**:
   Copy `.env.example` to `.env`.
   - Fill in `SECRET_KEY` and `ENCRYPTION_KEY`.
   - Paste the Neon connection string as `DATABASE_URL`.
   - **Never commit `.env` to version control.** It contains your database credentials and encryption keys.
   - If deploying to Render or another host, add `DATABASE_URL` as a secret environment variable in their dashboard.

3. **Initialize the database (Demo Setup)**:
   To create the necessary database tables and generate demo users, run the seed script:
   ```bash
   python seed.py
   ```
   **Important Security Note**: The `seed.py` script generates *random* secure passwords and fresh MFA secrets for the demo users. It will save these credentials to a local file named `.demo_credentials.txt`.
   - Read this file to get your login details.
   - Use the MFA Secret to set up your Authenticator app, or use a quick Python script to generate a TOTP code (instructions are inside the file).
   - **Delete `.demo_credentials.txt` immediately after securing your access.** It is ignored by Git, but it should not be kept on disk.

4. **Run the server**:
   ```bash
   python run.py
   ```

## Deployment

Please see [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) for detailed instructions on deploying this application safely to AWS EC2 using Gunicorn, Nginx, and PostgreSQL.
