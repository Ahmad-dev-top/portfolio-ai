"""Passphrase verification and signed session tokens.

The passphrase itself is never stored — only a salted PBKDF2 hash, and only
in .env. Run this file directly to generate that hash:

    python -m app.auth "your passphrase"
"""
import hashlib
import hmac
import secrets
import sys
import time

import jwt

ITERATIONS = 240_000


def hash_passphrase(passphrase: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), bytes.fromhex(salt), ITERATIONS)
    # Use ":" — "$" is eaten by Docker Compose / dotenv variable expansion.
    return f"{salt}:{dk.hex()}"


def verify_passphrase(passphrase: str, stored: str) -> bool:
    stored = stored.strip().strip("'").strip('"')
    try:
        if ":" in stored:
            salt, expected = stored.split(":", 1)
        else:
            salt, expected = stored.split("$", 1)  # legacy hashes
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), bytes.fromhex(salt), ITERATIONS)
    return hmac.compare_digest(dk.hex(), expected)      # constant time


def issue_token(secret: str, hours: int = 2) -> str:
    now = int(time.time())
    return jwt.encode({"sub": "admin", "iat": now, "exp": now + hours * 3600},
                      secret, algorithm="HS256")


def valid_token(token: str, secret: str) -> bool:
    try:
        jwt.decode(token, secret, algorithms=["HS256"])
        return True
    except jwt.PyJWTError:
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit('Usage: python -m app.auth "your passphrase"')
    print(hash_passphrase(sys.argv[1]))
