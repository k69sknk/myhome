"""Lecture du registre des appareils Home Assistant (add-on vers Core)."""

from __future__ import annotations

import json
import os
from typing import Any

from .schemas import HaDeviceOut


class HaUnavailableError(Exception):
    """Supervisor ou Core injoignable (dev local, token absent)."""


def list_ha_devices() -> list[HaDeviceOut]:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise HaUnavailableError("SUPERVISOR_TOKEN absent")

    try:
        from websockets.sync.client import connect
    except ImportError as exc:  # pragma: no cover
        raise HaUnavailableError("client websocket indisponible") from exc

    url = os.environ.get("HOMEKEEPER_HA_WS_URL", "ws://supervisor/core/websocket")
    try:
        with connect(url, open_timeout=5, close_timeout=5) as ws:
            hello = json.loads(ws.recv())
            if hello.get("type") != "auth_required":
                raise HaUnavailableError("handshake Home Assistant inattendu")
            ws.send(json.dumps({"type": "auth", "access_token": token}))
            auth = json.loads(ws.recv())
            if auth.get("type") != "auth_ok":
                raise HaUnavailableError("authentification Core refusee")

            devices = _ws_command(ws, 1, {"type": "config/device_registry/list"})
            entities = _ws_command(ws, 2, {"type": "config/entity_registry/list"})
            areas = _ws_command(ws, 3, {"type": "config/area_registry/list"})
    except HaUnavailableError:
        raise
    except Exception as exc:
        raise HaUnavailableError(str(exc)) from exc

    area_names = {item.get("area_id"): item.get("name") for item in areas if isinstance(item, dict)}
    primary_entity: dict[str, dict[str, Any]] = {}
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        device_id = entity.get("device_id")
        if not device_id or device_id in primary_entity:
            continue
        primary_entity[str(device_id)] = entity

    result: list[HaDeviceOut] = []
    for device in devices:
        if not isinstance(device, dict) or device.get("disabled_by"):
            continue
        device_id = str(device.get("id") or "")
        if not device_id:
            continue
        entity = primary_entity.get(device_id, {})
        name = device.get("name_by_user") or device.get("name") or entity.get("name") or device_id
        result.append(
            HaDeviceOut(
                ha_device_id=device_id,
                name=str(name),
                manufacturer=device.get("manufacturer"),
                model=device.get("model"),
                area_name=area_names.get(device.get("area_id")),
                entity_id=entity.get("entity_id"),
                domain=entity.get("domain")
                or (str(entity.get("entity_id", "")).split(".", 1)[0] or None),
            )
        )
    result.sort(key=lambda item: item.name.lower())
    return result


def _ws_command(ws: Any, msg_id: int, payload: dict[str, Any]) -> list[Any]:
    ws.send(json.dumps({"id": msg_id, **payload}))
    while True:
        message = json.loads(ws.recv())
        if message.get("id") != msg_id:
            continue
        if not message.get("success"):
            raise HaUnavailableError(str(message.get("error") or "commande websocket echouee"))
        result = message.get("result")
        return result if isinstance(result, list) else []
