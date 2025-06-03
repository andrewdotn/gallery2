from django.apps import AppConfig

from pillow_heif import register_heif_opener

register_heif_opener()


class Gallery2Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "gallery2"
