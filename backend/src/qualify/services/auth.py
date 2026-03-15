import secrets

_TOKEN: str = secrets.token_urlsafe(32)


def get_token() -> str:
    return _TOKEN


def verify_token(token: str) -> bool:
    return bool(token) and secrets.compare_digest(token, _TOKEN)
