import keyring

_SERVICE = "qualify"


def store_sudo_password(server_id: str, password: str) -> None:
    keyring.set_password(_SERVICE, f"{server_id}:sudo", password)


def get_sudo_password(server_id: str) -> str | None:
    return keyring.get_password(_SERVICE, f"{server_id}:sudo")


def delete_sudo_password(server_id: str) -> None:
    try:
        keyring.delete_password(_SERVICE, f"{server_id}:sudo")
    except keyring.errors.PasswordDeleteError:
        pass


def store_cloudflare_token(token: str) -> None:
    keyring.set_password(_SERVICE, "cloudflare_token", token)


def get_cloudflare_token() -> str | None:
    return keyring.get_password(_SERVICE, "cloudflare_token")


def delete_cloudflare_token() -> None:
    try:
        keyring.delete_password(_SERVICE, "cloudflare_token")
    except keyring.errors.PasswordDeleteError:
        pass
