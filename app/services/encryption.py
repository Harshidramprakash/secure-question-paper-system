"""Encryption service for secure multi-party question paper assembly.

Provides AES-256-GCM encryption and SHA-256 integrity verification.
Key management is handled by a pluggable key provider (local or AWS KMS).
"""
import os
import hashlib
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""
    pass


def _get_key() -> bytes:
    """Retrieve the 32-byte AES key using the configured key provider.

    Uses LocalKeyProvider by default (reads ENCRYPTION_KEY from app config).
    Switches to AWSKMSKeyProvider when KMS_KEY_ID is set.
    """
    from .key_provider import LocalKeyProvider, get_key_provider, KeyProviderError

    try:
        # First try the app config (needed for Flask test contexts)
        key_hex = current_app.config.get('ENCRYPTION_KEY')
        if key_hex:
            provider = LocalKeyProvider(key_hex=key_hex)
            return provider.get_key()

        # Fall back to env-based provider selection (KMS or local)
        provider = get_key_provider()
        return provider.get_key()
    except KeyProviderError as e:
        raise EncryptionError(str(e))



def encrypt_content(plaintext: str) -> tuple[bytes, bytes]:
    """Encrypt plaintext using AES-256-GCM.
    
    Args:
        plaintext: The text content to encrypt.
        
    Returns:
        A tuple of (ciphertext_with_tag, nonce).
        The tag is appended to the ciphertext automatically by AESGCM.
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    
    # Generate a unique 12-byte nonce for every encryption operation
    nonce = os.urandom(12)
    
    plaintext_bytes = plaintext.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
    
    return ciphertext, nonce


def decrypt_content(ciphertext: bytes, nonce: bytes) -> str:
    """Decrypt ciphertext using AES-256-GCM.
    
    Args:
        ciphertext: The encrypted data (including the auth tag at the end).
        nonce: The 12-byte nonce used during encryption.
        
    Returns:
        The decrypted plaintext string.
        
    Raises:
        EncryptionError: If authentication fails (e.g. data or nonce tampered).
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    
    try:
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode('utf-8')
    except Exception as e:
        raise EncryptionError(f"Decryption failed (authentication tag check failed or invalid data). {e}")


def compute_hash(content: str) -> str:
    """Compute the SHA-256 hash of the content.
    
    Args:
        content: The plaintext content.
        
    Returns:
        The hexadecimal digest of the hash.
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def verify_integrity(content: str, expected_hash: str) -> bool:
    """Verify if the content matches the expected SHA-256 hash.
    
    Args:
        content: The plaintext content.
        expected_hash: The previously computed hex hash.
        
    Returns:
        True if the hashes match, False otherwise.
    """
    return compute_hash(content) == expected_hash
