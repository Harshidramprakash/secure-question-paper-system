"""Key management abstraction for encryption key provisioning.

Provides two key providers:

1. LocalKeyProvider  — Reads a hex-encoded key from the ENCRYPTION_KEY
                       environment variable. Used for local development and tests.

2. AWSKMSKeyProvider — Uses AWS KMS to decrypt an encrypted data key (envelope
                       encryption). Uses IAM role authentication (no hardcoded
                       AWS credentials). Used for AWS production deployment.

Security:
    - Never log plaintext keys, ciphertext, or decrypted content.
    - The AWS provider uses IAM instance profile / role for auth.
    - KMS_KEY_ID and AWS_REGION are read from environment variables.

Usage:
    provider = get_key_provider()
    key_bytes = provider.get_key()  # Returns 32-byte AES key
"""
import abc
import logging
import os

logger = logging.getLogger(__name__)


class KeyProviderError(Exception):
    """Raised when a key provider cannot supply the encryption key."""
    pass


class BaseKeyProvider(abc.ABC):
    """Abstract base class for encryption key providers."""

    @abc.abstractmethod
    def get_key(self) -> bytes:
        """Return the 32-byte AES-256 encryption key.

        Returns:
            bytes: A 32-byte key suitable for AES-256-GCM.

        Raises:
            KeyProviderError: If the key cannot be obtained.
        """
        ...

    @abc.abstractmethod
    def provider_name(self) -> str:
        """Return a human-readable name for this provider (for logging)."""
        ...


class LocalKeyProvider(BaseKeyProvider):
    """Reads the encryption key from the ENCRYPTION_KEY config/env var.

    The key must be a 64-character hex string (encoding 32 bytes).
    This is the default provider for development and testing.
    """

    def __init__(self, key_hex: str | None = None):
        self._key_hex = key_hex

    def get_key(self) -> bytes:
        key_hex = self._key_hex or os.environ.get('ENCRYPTION_KEY')
        if not key_hex:
            raise KeyProviderError(
                'ENCRYPTION_KEY is not configured. '
                'Set it in your .env file or environment variables.'
            )
        try:
            key = bytes.fromhex(key_hex)
            if len(key) != 32:
                raise ValueError('Key must be exactly 32 bytes.')
            return key
        except ValueError as e:
            raise KeyProviderError(
                f'ENCRYPTION_KEY must be a 64-character valid hex string: {e}'
            )

    def provider_name(self) -> str:
        return 'LocalKeyProvider'


class AWSKMSKeyProvider(BaseKeyProvider):
    """Uses AWS KMS for envelope encryption of the data encryption key.

    Architecture (Envelope Encryption):
        1. A Data Encryption Key (DEK) is generated via KMS GenerateDataKey.
        2. The plaintext DEK encrypts application data (AES-256-GCM).
        3. The encrypted DEK is stored alongside the application.
        4. At startup, KMS Decrypt is called to recover the plaintext DEK.

    For this college demo, the provider can also simply use KMS to decrypt
    the ENCRYPTION_KEY if it was encrypted with KMS and stored as a
    base64-encoded ciphertext blob in the ENCRYPTED_DATA_KEY env var.

    If ENCRYPTED_DATA_KEY is not set, falls back to LocalKeyProvider behavior
    (reading ENCRYPTION_KEY directly) — but logs a warning.

    Environment Variables:
        AWS_REGION   — AWS region (e.g. 'ap-south-1')
        KMS_KEY_ID   — KMS key ARN or alias
        ENCRYPTED_DATA_KEY — (Optional) base64-encoded encrypted DEK

    Authentication:
        Uses IAM role attached to the EC2 instance — no hardcoded credentials.
    """

    def __init__(self):
        self._region = os.environ.get('AWS_REGION', 'ap-south-1')
        self._kms_key_id = os.environ.get('KMS_KEY_ID', '')
        self._cached_key: bytes | None = None

    def get_key(self) -> bytes:
        if self._cached_key is not None:
            return self._cached_key

        encrypted_dek_b64 = os.environ.get('ENCRYPTED_DATA_KEY')

        if encrypted_dek_b64:
            # Envelope encryption mode — decrypt the DEK via KMS
            self._cached_key = self._decrypt_dek(encrypted_dek_b64)
        else:
            # Fallback: read plaintext key from env (not ideal for production)
            logger.warning(
                'AWSKMSKeyProvider: ENCRYPTED_DATA_KEY not set, '
                'falling back to plaintext ENCRYPTION_KEY env var. '
                'For production, use envelope encryption with KMS.'
            )
            fallback = LocalKeyProvider()
            self._cached_key = fallback.get_key()

        return self._cached_key

    def _decrypt_dek(self, encrypted_dek_b64: str) -> bytes:
        """Decrypt the data encryption key using AWS KMS."""
        import base64

        try:
            import boto3
        except ImportError:
            raise KeyProviderError(
                'boto3 is required for AWS KMS integration. '
                'Install it with: pip install boto3'
            )

        try:
            encrypted_dek = base64.b64decode(encrypted_dek_b64)
            kms_client = boto3.client('kms', region_name=self._region)

            response = kms_client.decrypt(
                CiphertextBlob=encrypted_dek,
                KeyId=self._kms_key_id,
            )

            plaintext_key = response['Plaintext']
            if len(plaintext_key) != 32:
                raise KeyProviderError(
                    f'KMS returned a key of {len(plaintext_key)} bytes; expected 32.'
                )

            logger.info('AWSKMSKeyProvider: Data encryption key decrypted via KMS.')
            return plaintext_key

        except KeyProviderError:
            raise
        except Exception as e:
            raise KeyProviderError(
                f'Failed to decrypt data key via AWS KMS: {type(e).__name__}'
            )

    def provider_name(self) -> str:
        return 'AWSKMSKeyProvider'


def get_key_provider() -> BaseKeyProvider:
    """Factory function — returns the appropriate key provider.

    Uses AWSKMSKeyProvider if KMS_KEY_ID is set, otherwise LocalKeyProvider.
    """
    kms_key_id = os.environ.get('KMS_KEY_ID')
    if kms_key_id:
        logger.info('Using AWSKMSKeyProvider for encryption key management.')
        return AWSKMSKeyProvider()
    else:
        logger.info('Using LocalKeyProvider for encryption key management.')
        return LocalKeyProvider()
