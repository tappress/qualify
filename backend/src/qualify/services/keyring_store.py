import keyring
import keyring.errors

_SERVICE = "qualify"


def _get(key: str) -> str | None:
    try:
        return keyring.get_password(_SERVICE, key)
    except Exception:
        return None


def _set(key: str, value: str) -> None:
    try:
        keyring.set_password(_SERVICE, key, value)
    except Exception:
        pass  # keyring unavailable in headless environments


def _delete(key: str) -> None:
    try:
        keyring.delete_password(_SERVICE, key)
    except Exception:
        pass


def store_sudo_password(server_id: str, password: str) -> None:
    _set(f"{server_id}:sudo", password)


def get_sudo_password(server_id: str) -> str | None:
    return _get(f"{server_id}:sudo")


def delete_sudo_password(server_id: str) -> None:
    _delete(f"{server_id}:sudo")


def store_cloudflare_token(token: str) -> None:
    _set("cloudflare_token", token)


def get_cloudflare_token() -> str | None:
    return _get("cloudflare_token")


def delete_cloudflare_token() -> None:
    _delete("cloudflare_token")


def store_registry_password(server_id: str, password: str) -> None:
    _set(f"{server_id}:registry_password", password)


def get_registry_password(server_id: str) -> str | None:
    return _get(f"{server_id}:registry_password")
