from fastapi import APIRouter
from qualify.models.state import AppSettings, SettingsUpdate
from qualify.services import state_manager
from qualify.services.keyring_store import (
    delete_cloudflare_token, store_cloudflare_token,
)

router = APIRouter()


@router.get("/", response_model=AppSettings)
async def get_settings():
    state = await state_manager.get_state()
    return state.settings


@router.put("/", response_model=AppSettings)
async def update_settings(body: SettingsUpdate):
    state = await state_manager.get_state()
    if body.primary_server_id is not None:
        state.settings.primary_server_id = body.primary_server_id
    if body.registry is not None:
        state.settings.registry = body.registry
    if body.cloudflare_zone_id is not None:
        state.settings.cloudflare_zone_id = body.cloudflare_zone_id
    if body.cloudflare_token is not None:
        if body.cloudflare_token == "":
            delete_cloudflare_token()
            state.settings.cloudflare_token_stored = False
        else:
            store_cloudflare_token(body.cloudflare_token)
            state.settings.cloudflare_token_stored = True
    await state_manager.update_settings(state.settings)
    return state.settings
