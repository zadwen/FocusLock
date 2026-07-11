"""Password hashing helpers."""

import hashlib
import os


def hash_password(password, salt=None):
    """Hash a password with an optional salt using SHA-256.

    Returns ``"salt:hash"`` if a salt is provided, otherwise the raw hex
    digest (for backwards compatibility with existing stored hashes).
    """
    if salt is None:
        salt = os.urandom(16)
    else:
        if isinstance(salt, str) and ":" in salt:
            return salt  # already hashed
        if isinstance(salt, str):
            salt = bytes.fromhex(salt)
    hashed = hashlib.sha256(salt + password.encode()).hexdigest()
    return f"{salt.hex()}:{hashed}"


def verify_password(password, stored):
    """Verify *password* against a *stored* hash produced by :func:`hash_password`."""
    if not stored:
        return False
    if ":" not in stored:
        # Legacy unsalted hash – compare directly (one-way migration)
        return hashlib.sha256(password.encode()).hexdigest() == stored
    salt_hex, expected = stored.split(":", 1)
    salt = bytes.fromhex(salt_hex)
    actual = hashlib.sha256(salt + password.encode()).hexdigest()
    return actual == expected
