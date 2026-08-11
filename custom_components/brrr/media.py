"""Resolve Home Assistant Media Library images for Brrr."""

from __future__ import annotations

import mimetypes
import secrets
import shutil
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlsplit

from homeassistant.components import media_source
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import MAX_MEDIA_BYTES, MEDIA_CACHE_DIRECTORY


class BrrrMediaError(ValueError):
    """Raised when selected media cannot safely be exposed to Brrr."""


async def async_cleanup_media_cache(
    hass: HomeAssistant,
    ttl_hours: int,
    *,
    remove_all: bool = False,
) -> int:
    """Remove expired or all generated public-media files."""
    cache_dir = Path(hass.config.path("www", MEDIA_CACHE_DIRECTORY))
    return await hass.async_add_executor_job(
        _cleanup_cache,
        cache_dir,
        ttl_hours,
        remove_all,
    )


async def async_resolve_media_image(
    hass: HomeAssistant,
    selection: Mapping[str, Any],
    *,
    public_media_enabled: bool,
    ttl_hours: int,
) -> str:
    """Resolve a media selector value into a public HTTPS URL."""
    media_content_id = selection.get("media_content_id")
    if not isinstance(media_content_id, str) or not media_content_id:
        raise BrrrMediaError("The selected Media Library item has no content ID")

    resolved = await media_source.async_resolve_media(
        hass,
        media_content_id,
        target_media_player=None,
    )

    parsed = urlsplit(resolved.url)
    if parsed.scheme == "https" and parsed.netloc:
        return resolved.url
    if parsed.scheme and parsed.scheme != "https":
        raise BrrrMediaError("Brrr media URLs must use HTTPS")

    source_path = Path(resolved.path) if resolved.path else None
    if source_path is None:
        raise BrrrMediaError(
            "This Media Library item cannot be exported. "
            "Use an HTTPS image URL instead."
        )
    if not public_media_enabled:
        raise BrrrMediaError(
            "Public Media Library export is disabled in the Brrr integration settings"
        )

    try:
        base_url = get_url(hass, prefer_external=True)
    except NoURLAvailableError as err:
        raise BrrrMediaError(
            "Home Assistant needs an externally reachable HTTPS URL to export media"
        ) from err
    base_parts = urlsplit(base_url)
    if base_parts.scheme != "https" or not base_parts.netloc:
        raise BrrrMediaError(
            "Home Assistant needs an externally reachable HTTPS URL to export media"
        )

    cache_dir = Path(hass.config.path("www", MEDIA_CACHE_DIRECTORY))
    cached_name = await hass.async_add_executor_job(
        _cache_media_file,
        source_path,
        cache_dir,
        resolved.mime_type,
        ttl_hours,
    )
    return urljoin(
        base_url.rstrip("/") + "/",
        f"local/{MEDIA_CACHE_DIRECTORY}/{cached_name}",
    )


def _cache_media_file(
    source_path: Path,
    cache_dir: Path,
    mime_type: str | None,
    ttl_hours: int,
) -> str:
    """Copy an image into HA's unauthenticated www directory."""
    if not source_path.is_file():
        raise BrrrMediaError("The selected Media Library file no longer exists")

    size = source_path.stat().st_size
    if size > MAX_MEDIA_BYTES:
        raise BrrrMediaError("Selected image is larger than 10 MB")

    cache_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_cache(cache_dir, ttl_hours)

    suffix = source_path.suffix.lower()
    if not suffix and mime_type:
        suffix = mimetypes.guess_extension(mime_type) or ""
    if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic"}:
        raise BrrrMediaError("Selected media must be a supported image file")

    filename = f"{secrets.token_urlsafe(24)}{suffix}"
    destination = cache_dir / filename
    shutil.copyfile(source_path, destination)
    return filename


def _cleanup_cache(
    cache_dir: Path,
    ttl_hours: int,
    remove_all: bool = False,
) -> int:
    """Remove expired generated public-media files."""
    if not cache_dir.is_dir():
        return 0

    cutoff = time.time() - max(ttl_hours, 1) * 3600
    removed = 0
    for item in cache_dir.iterdir():
        try:
            should_remove = item.is_file() and (
                remove_all or item.stat().st_mtime < cutoff
            )
        except FileNotFoundError:
            continue
        if should_remove:
            item.unlink(missing_ok=True)
            removed += 1
    return removed
