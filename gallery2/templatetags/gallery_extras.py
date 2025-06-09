from django import template
from django.utils.safestring import mark_safe
import markdown
from pathlib import Path

register = template.Library()


@register.filter
def markdown_to_html(text):
    """
    Convert markdown text to HTML.
    Usage: {{ caption|markdown_to_html }}
    """
    if text:
        return mark_safe(markdown.markdown(text))
    return ""


@register.simple_tag
def scale_dimensions(width, height, max_size=800):
    """
    Scale width and height proportionally for thumbnail display.
    Usage: {% scale_dimensions entry.width entry.height 800 as scaled %}
           width="{{ scaled.width }}" height="{{ scaled.height }}"
    """
    if width is None or height is None:
        return {"width": "", "height": ""}

    if width <= max_size:
        return {"width": width, "height": height}

    scale_factor = max_size / width
    scaled_width = int(max_size)
    scaled_height = int(height * scale_factor)

    return {"width": scaled_width, "height": scaled_height}


@register.filter
def has_video(filenames):
    """
    Check if any of the filenames in the list has a video extension.
    Usage: {{ entry.filenames|has_video }}
    Returns True if any filename has a .mov extension.
    """
    if not filenames:
        return False

    VIDEO_EXTENSIONS = [".mov", ".mp4", ".avi", ".mkv"]

    for filename in filenames:
        ext = Path(filename).suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            return True

    return False


@register.filter
def get_video_filename(filenames):
    """
    Get the first video filename from the list.
    Usage: {{ entry.filenames|get_video_filename }}
    Returns the first filename with a video extension, or None if no video file is found.
    """
    if not filenames:
        return None

    VIDEO_EXTENSIONS = [".mov", ".mp4", ".avi", ".mkv"]

    for filename in filenames:
        ext = Path(filename).suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            return filename

    return None
