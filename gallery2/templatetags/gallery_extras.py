from django import template
from django.utils.safestring import mark_safe
import markdown

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
