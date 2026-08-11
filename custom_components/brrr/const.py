"""Constants for the Brrr Notifications integration."""

from __future__ import annotations

DOMAIN = "brrr"

CONF_WEBHOOK_KEY = "webhook_key"
CONF_PUBLIC_MEDIA_ENABLED = "public_media_enabled"
CONF_PUBLIC_MEDIA_TTL_HOURS = "public_media_ttl_hours"

DEFAULT_NAME = "Brrr"
DEFAULT_PUBLIC_MEDIA_TTL_HOURS = 24

SERVICE_SEND_NOTIFICATION = "send_notification"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_TITLE = "title"
ATTR_SUBTITLE = "subtitle"
ATTR_MESSAGE = "message"
ATTR_THREAD_ID = "thread_id"
ATTR_SOUND = "sound"
ATTR_OPEN_URL = "open_url"
ATTR_IMAGE_URL = "image_url"
ATTR_IMAGE_MEDIA = "image_media"
ATTR_ICON_URL = "icon_url"
ATTR_ICON_MEDIA = "icon_media"
ATTR_EXPIRATION_DATE = "expiration_date"
ATTR_FILTER_CRITERIA = "filter_criteria"
ATTR_INTERRUPTION_LEVEL = "interruption_level"
ATTR_VOLUME = "volume"

API_ENDPOINT = "https://api.brrr.now/v1/send"
API_TIMEOUT_SECONDS = 10

MEDIA_CACHE_DIRECTORY = "brrr"
MAX_MEDIA_BYTES = 10 * 1024 * 1024

SOUNDS = {
    "default",
    "system",
    "brrr",
    "bell_ringing",
    "bubble_ding",
    "bubbly_success_ding",
    "cat_meow",
    "calm1",
    "calm2",
    "cha_ching",
    "dog_barking",
    "door_bell",
    "duck_quack",
    "emergency",
    "short_triple_blink",
    "upbeat_bells",
    "warm_soft_error",
}

INTERRUPTION_LEVELS = {"passive", "active", "time-sensitive", "critical"}
