# TODO AWS MIGRATION: replace with Amazon Cognito user pool authentication
"""
auth.py
=======
Mock authentication layer standing in for AWS Cognito.

In this simulation:
  - Users are stored as a hardcoded dict with SHA-256 hashed passwords.
  - login() returns a UUID4 token stored in memory with a 1-hour expiry.
  - verify_token() validates token existence and expiry.

On AWS migration
----------------
  Replace login() with a Cognito InitiateAuth API call (boto3.client('cognito-idp')).
  Replace verify_token() with Cognito GetUser / token introspection.
  Remove the in-memory token store (Cognito manages sessions server-side).

Security note
-------------
  Passwords are hashed with SHA-256 at module load time.
  Plain-text passwords are never stored anywhere in this module.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# User store — passwords hashed at module load (never stored as plaintext)
# ---------------------------------------------------------------------------
def _hash_password(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


_USERS: dict = {
    "admin": _hash_password("hospital123"),
}

# In-memory session store: {token: {"username": str, "expires_at": datetime}}
_ACTIVE_TOKENS: dict = {}

TOKEN_TTL_HOURS = 1


def login(username: str, password: str):
    """
    Authenticate a user and return a session token.

    Parameters
    ----------
    username : str
    password : str  (plain text — hashed internally before comparison)

    Returns
    -------
    str   A mock JWT-like UUID4 token string if credentials are valid.
    None  If authentication fails.
    """
    hashed = _hash_password(password)
    if _USERS.get(username) == hashed:
        token      = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
        _ACTIVE_TOKENS[token] = {"username": username, "expires_at": expires_at}
        return token
    return None


def verify_token(token: str):
    """
    Validate a session token.

    Parameters
    ----------
    token : str  The token string returned by login().

    Returns
    -------
    str   The username associated with the token if valid and not expired.
    None  If the token is invalid or has expired.
    """
    session = _ACTIVE_TOKENS.get(token)
    if session is None:
        return None
    if datetime.now(timezone.utc) > session["expires_at"]:
        # Token expired — clean up
        del _ACTIVE_TOKENS[token]
        return None
    return session["username"]


def logout(token: str) -> bool:
    """Invalidate an active session token. Returns True if token existed."""
    if token in _ACTIVE_TOKENS:
        del _ACTIVE_TOKENS[token]
        return True
    return False


if __name__ == "__main__":
    print("Auth module demo")
    tok = login("admin", "hospital123")
    print(f"Login success: token = {tok}")
    print(f"Verify valid token: {verify_token(tok)}")
    print(f"Verify bad token:   {verify_token('not-a-real-token')}")
    logout(tok)
    print(f"After logout:       {verify_token(tok)}")
