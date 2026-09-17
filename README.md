# Secure Multi-Party Question Paper Assembly System (SQPAS)

SQPAS is a security-focused Flask application for the secure creation, multi-party assembly, approval, and controlled release of examination question papers.

The system implements:

- Role-Based Access Control (RBAC)
- AES-256-GCM encryption
- Multi-party question paper assembly
- Multi-Factor Authentication (MFA)
- TOTP-based authentication
- Recovery-code-based MFA recovery
- Secure approval workflow
- Controlled examination paper release
- Audit logging and security monitoring
- PostgreSQL database support

## Live Deployment

Application URL:

[Open SQPAS](https://secure-question-paper-system.onrender.com/auth/login)

> **Note:** The deployed application is intended for demonstration and academic project purposes. Do not use it for real examination operations without a complete security audit, operational controls, and proper deployment hardening.

## Application Overview

SQPAS provides a controlled platform for examination authorities to manage the end-to-end process of question paper preparation.

The workflow includes:

1. Admin creates an examination paper.
2. Admin creates sections and assigns question setters.
3. Setters prepare their assigned sections independently.
4. Setters submit completed sections for approval.
5. Authorized users review and approve the sections.
6. The system assembles the approved sections.
7. The final question paper is encrypted and stored securely.
8. The examination officer releases the paper only after the configured release time.
9. The released paper is decrypted in memory for authorized access.

## User Roles

| Username | Role | Responsibility |
|---|---|---|
| `admin` | Administrator | Manage users, papers, assignments, and system settings |
| `officer` | Examination Officer | Manage approval and controlled release |
| `setter_a` | Question Setter A | Prepare assigned question paper sections |
| `setter_b` | Question Setter B | Prepare assigned question paper sections |

> Demo passwords and MFA setup details are generated locally by `seed.py` and stored in `.demo_credentials.txt`.

> **Security warning:** Never commit, upload, or publicly share `.demo_credentials.txt`. These credentials are intended only for local demonstration. Change all demo credentials before any real deployment.

## Security Features

### Authentication and Authorization

- Role-Based Access Control
- Password-protected login
- TOTP-based Multi-Factor Authentication
- Recovery codes for MFA account recovery
- Password re-verification for sensitive operations
- Role-specific dashboards and permissions

### Data Protection

- AES-256-GCM encryption for question paper content
- Unique nonce generation
- Authentication tags for encrypted data integrity
- SHA-256 hashing for integrity verification
- Encryption keys and secret keys loaded through environment variables

### Workflow Security

- Independent question setter assignments
- Multi-party section preparation
- Controlled approval process
- Time-based paper release
- Restricted access to released question papers
- Audit logging for important actions

## Local Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/Harshidramprakash/secure-question-paper-system.git
cd secure-question-paper-system