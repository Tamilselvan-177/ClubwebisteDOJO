"""
JWT RS256 issuance for Dojo SSO.
Club website acts as Identity Provider; CTF platform consumes tokens.
"""
import time
from django.conf import settings

def get_private_key():
    """Load RS256 private key from DOJO_JWT_PRIVATE_KEY path or PEM string."""
    key_path = getattr(settings, 'DOJO_JWT_PRIVATE_KEY_PATH', None)
    if key_path:
        try:
            with open(key_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return None
    return getattr(settings, 'DOJO_JWT_PRIVATE_KEY_PEM', None)


def issue_dojo_token(user, expires_seconds=None):
    """
    Issue a JWT for the given user to be consumed by the CTF (Dojo) platform.
    Uses RS256; CTF validates with public key.
    """
    import jwt
    pem = get_private_key()
    if not pem:
        return None
    expires_seconds = expires_seconds or getattr(settings, 'DOJO_JWT_EXPIRES_SECONDS', 300)
    now = int(time.time())
    payload = {
        'user_id': user.pk,
        'username': user.get_username(),
        'email': getattr(user, 'email', None) or getattr(user, 'username', ''),
        'role': 'member',  # optional
        'iss': getattr(settings, 'DOJO_JWT_ISSUER', 'cyber-sentinels-club'),
        'aud': getattr(settings, 'DOJO_JWT_AUDIENCE', 'cyber-sentinels-ctf'),
        'iat': now,
        'exp': now + expires_seconds,
    }
    if hasattr(user, 'first_name') and user.first_name:
        payload['first_name'] = user.first_name
    if hasattr(user, 'last_name') and user.last_name:
        payload['last_name'] = user.last_name
    return jwt.encode(
        payload,
        pem,
        algorithm='RS256',
    )
