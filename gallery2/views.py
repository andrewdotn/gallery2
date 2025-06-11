import json
import mimetypes
from pathlib import Path

from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, CreateView, DetailView

from .models import Gallery, Entry
from .templatetags.gallery_extras import markdown_to_html
from .thumbnails import (
    get_thumbnail_extractor,
    ImageThumbnailExtractor,
    VideoThumbnailExtractor,
)

mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("video/quicktime", ".mov")
mimetypes.add_type("image/webp", ".webp")


class GalleryListView(ListView):
    model = Gallery
    context_object_name = "galleries"


class GalleryDetailView(DetailView):
    model = Gallery
    context_object_name = "gallery"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entries"] = Entry.objects.filter(gallery=self.object).order_by("order")
        return context


class GalleryCreateView(CreateView):
    model = Gallery
    fields = ["name"]
    success_url = reverse_lazy("gallery2:gallery_list")


def entry_thumbnail(request, entry_id, size=800, hidden_thumbnail_size=100):
    """
    Generate and serve a thumbnail for an entry.

    Uses the appropriate thumbnail extractor based on the file type.
    For image files (png/jpeg/heic), uses PIL to create a thumbnail.
    For video files, extracts a frame to use as a thumbnail.

    Returns:
        FileResponse with the thumbnail image
    """
    entry = get_object_or_404(Entry, pk=entry_id)
    gallery = entry.gallery

    if entry.hidden:
        size = hidden_thumbnail_size

    # Get the appropriate thumbnail extractor
    extractor = get_thumbnail_extractor(entry.filenames, gallery.id, entry.id, size)
    if not extractor:
        raise Http404(
            f"No suitable thumbnail extractor found for files: {entry.filenames}"
        )

    # Check if thumbnail already exists
    thumbnail_path = extractor.get_thumbnail_path()
    if not thumbnail_path.exists():
        # Find the first file that the extractor can handle
        original_filename = None
        for filename in entry.filenames:
            # Use the extractor's can_handle method to find a suitable file
            if (
                isinstance(extractor, ImageThumbnailExtractor)
                and ImageThumbnailExtractor.can_handle(filename)
            ) or (
                isinstance(extractor, VideoThumbnailExtractor)
                and VideoThumbnailExtractor.can_handle(filename)
            ):
                original_filename = filename
                break

        if not original_filename:
            raise Http404(f"No suitable file found for thumbnail extraction")

        original_path = Path(gallery.directory) / original_filename
        if not original_path.exists():
            raise Http404(f"Original file not found: {original_path}")

        thumbnail_path = extractor.get_thumbnail(original_path)

    return FileResponse(open(thumbnail_path, "rb"))


@require_http_methods(["POST"])
def edit_caption(request, entry_id):
    """
    REST JSON endpoint to edit the caption for a specific image entry.

    Args:
        request: The HTTP request object
        entry_id: The ID of the entry to edit

    Returns:
        JsonResponse with the updated entry data or an error message
    """
    try:
        entry = get_object_or_404(Entry, pk=entry_id)

        # Parse the JSON data from the request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)

        # Check if the caption field is present in the request
        if "caption" not in data:
            return JsonResponse({"error": "Caption field is required"}, status=400)

        # Update the caption
        entry.caption = data["caption"]
        entry.save()

        # Return the updated entry data with HTML-rendered caption
        return JsonResponse(
            {
                "id": entry.id,
                "gallery_id": entry.gallery_id,
                "basename": entry.basename,
                "caption": entry.caption,
                "html_caption": markdown_to_html(entry.caption),
                "order": entry.order,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            }
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["POST"])
def set_entry_hidden(request, entry_id):
    """
    REST JSON endpoint to set the 'hidden' status of an entry.
    Expects: { "hidden": true/false }
    """
    entry = get_object_or_404(Entry, pk=entry_id)
    try:
        data = json.loads(request.body)
        if "hidden" not in data:
            return JsonResponse({"error": "'hidden' field is required"}, status=400)
        entry.hidden = bool(data["hidden"])
        entry.save()
        return JsonResponse({"id": entry.id, "hidden": entry.hidden})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def entry_original(request, entry_id):
    """
    Serve the original file for an entry.
    Prioritizes image files over video files, similar to thumbnail extraction.

    Returns:
        FileResponse with the original file
    """
    entry = get_object_or_404(Entry, pk=entry_id)
    gallery = entry.gallery

    # First try to find an image file
    original_filename = None
    for filename in entry.filenames:
        if ImageThumbnailExtractor.can_handle(filename):
            original_path = Path(gallery.directory) / filename
            if original_path.exists():
                original_filename = filename
                break

    # If no image file is found, try to find a video file
    if not original_filename:
        for filename in entry.filenames:
            if VideoThumbnailExtractor.can_handle(filename):
                original_path = Path(gallery.directory) / filename
                if original_path.exists():
                    original_filename = filename
                    break

    if not original_filename:
        raise Http404(f"No original file found for entry {entry_id}")

    original_path = Path(gallery.directory) / original_filename

    # Determine content type using Python's mimetypes module
    content_type, encoding = mimetypes.guess_type(original_filename)
    if content_type is None:
        content_type = "application/octet-stream"  # Default

    return FileResponse(open(original_path, "rb"), content_type=content_type)


def entry_video(request, entry_id):
    entry = get_object_or_404(Entry, pk=entry_id)
    gallery = entry.gallery

    video_filename = None
    for filename in entry.filenames:
        if filename.lower().endswith(".mov"):
            video_path = Path(gallery.directory) / filename
            if video_path.exists():
                video_filename = filename
                break

    if not video_filename:
        raise Http404(f"No video file found for entry {entry_id}")

    video_path = Path(gallery.directory) / video_filename

    # Determine content type using Python's mimetypes module
    content_type, encoding = mimetypes.guess_type(video_filename)
    if content_type is None:
        content_type = "application/octet-stream"  # Default

    return FileResponse(open(video_path, "rb"), content_type=content_type)
