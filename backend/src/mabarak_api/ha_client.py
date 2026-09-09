"""Lecture du registre des appareils Home Assistant (add-on vers Core)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .schemas import HaCalendarOut, HaDeviceOut


class HaUnavailableError(Exception):
    """Supervisor ou Core injoignable (dev local, token absent)."""


def _rest_base_url() -> str:
    return os.environ.get("MABARAK_HA_REST_URL", "http://supervisor/core/api")


def _rest_headers() -> dict[str, str]:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise HaUnavailableError("SUPERVISOR_TOKEN absent")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def list_ha_calendars() -> list[HaCalendarOut]:
    """Liste les entites `calendar.*` connues de Home Assistant."""
    headers = _rest_headers()
    try:
        response = httpx.get(f"{_rest_base_url()}/states", headers=headers, timeout=10)
        response.raise_for_status()
        states = response.json()
    except httpx.HTTPError as exc:
        raise HaUnavailableError(str(exc)) from exc

    calendars: list[HaCalendarOut] = []
    for state in states:
        entity_id = str(state.get("entity_id") or "")
        if not entity_id.startswith("calendar."):
            continue
        attributes = state.get("attributes") or {}
        name = str(attributes.get("friendly_name") or entity_id)
        calendars.append(HaCalendarOut(entity_id=entity_id, name=name))
    calendars.sort(key=lambda item: item.name.lower())
    return calendars


def get_calendar_events(entity_id: str, start: str, end: str) -> list[dict[str, Any]]:
    """Evenements existants d'un calendrier HA sur une periode donnee."""
    headers = _rest_headers()
    try:
        response = httpx.get(
            f"{_rest_base_url()}/calendars/{entity_id}",
            headers=headers,
            params={"start": start, "end": end},
            timeout=10,
        )
        response.raise_for_status()
        events = response.json()
    except httpx.HTTPError as exc:
        raise HaUnavailableError(str(exc)) from exc
    return events if isinstance(events, list) else []


def call_ha_service(domain: str, service: str, data: dict[str, Any]) -> None:
    """Invoque un service Home Assistant (ex: calendar.create_event)."""
    headers = _rest_headers()
    try:
        response = httpx.post(
            f"{_rest_base_url()}/services/{domain}/{service}",
            headers=headers,
            json=data,
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HaUnavailableError(str(exc)) from exc


def list_ha_devices() -> list[HaDeviceOut]:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise HaUnavailableError("SUPERVISOR_TOKEN absent")

    try:
        from websockets.sync.client import connect
    except ImportError as exc:  # pragma: no cover
        raise HaUnavailableError("client websocket indisponible") from exc

    url = os.environ.get("MABARAK_HA_WS_URL", "ws://supervisor/core/websocket")
    try:
        with connect(url, open_timeout=5, close_timeout=5) as ws:
            hello = json.loads(ws.recv(timeout=10))
            if hello.get("type") != "auth_required":
                raise HaUnavailableError("handshake Home Assistant inattendu")
            ws.send(json.dumps({"type": "auth", "access_token": token}))
            auth = json.loads(ws.recv(timeout=10))
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
        message = json.loads(ws.recv(timeout=10))
        if message.get("id") != msg_id:
            continue
        if not message.get("success"):
            raise HaUnavailableError(str(message.get("error") or "commande websocket echouee"))
        result = message.get("result")
        return result if isinstance(result, list) else []
