from django.test import Client
from django.urls import reverse
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from django.http import Http404
from unittest import mock
import pytest
from datetime import datetime
from pathlib import Path

from gallery2.models import Gallery, Entry


def test_gallery_list_view(db, client):
    g1 = Gallery.objects.create(name="Test Gallery 1")
    g2 = Gallery.objects.create(name="Test Gallery 2")

    response = client.get(reverse("gallery2:gallery_list"))

    assert response.status_code == 200
    assert "gallery2/gallery_list.html" in [t.name for t in response.templates]

    assert "galleries" in response.context

    galleries = response.context["galleries"]
    assert galleries.count() == 2
    assert list(galleries) == [g1, g2]

    assert g1.name in response.text
    assert g2.name in response.text


def test_gallery_create_view_get(db, client):
    response = client.get(reverse("gallery2:gallery_create"))
    assert response.status_code == 200


def test_gallery_create_view_post_valid(db, client):
    response = client.post(
        reverse("gallery2:gallery_create"), data={"name": "New Test Gallery"}
    )

    assert response.status_code == 302
    assert response.url == reverse("gallery2:gallery_list")
    assert Gallery.objects.filter(name="New Test Gallery").exists()


def test_gallery_create_view_post_invalid(db, client):
    response = client.post(reverse("gallery2:gallery_create"), data={"name": ""})

    assert response.status_code == 200
    assert response.context["form"].errors
    assert not Gallery.objects.filter(name="").exists()


def test_gallery_detail_view(db, client):
    gallery = Gallery.objects.create(name="Test Gallery Detail")

    entry1 = Entry.objects.create(
        gallery=gallery,
        basename="image1",
        filenames=["image1.jpg"],
        order=2.0,
        caption="This is **bold** text",
    )
    entry2 = Entry.objects.create(
        gallery=gallery,
        basename="image2",
        filenames=["image2.jpg"],
        order=1.0,
        caption="This is *italic* text",
    )
    entry3 = Entry.objects.create(
        gallery=gallery,
        basename="image3",
        filenames=["image3.jpg"],
        order=3.0,
        caption="This is a [link](http://example.com)",
    )

    response = client.get(reverse("gallery2:gallery_detail", kwargs={"pk": gallery.pk}))

    assert response.status_code == 200
    assert "gallery2/gallery_detail.html" in [t.name for t in response.templates]

    assert "gallery" in response.context
    assert response.context["gallery"] == gallery
    assert gallery.name in response.text

    assert "entries" in response.context
    entries = response.context["entries"]
    assert entries.count() == 3

    assert list(entries) == [entry2, entry1, entry3]

    assert entry1.basename in response.text
    assert entry2.basename in response.text
    assert entry3.basename in response.text

    # Check markdown is interpreted (HTML tags are generated)
    assert "<strong>bold</strong>" in response.text
    assert "<em>italic</em>" in response.text
    assert '<a href="http://example.com">link</a>' in response.text


# Tests for import_images management command
@mock.patch("pathlib.Path")
def test_import_images_success(mock_path, db):
    """Test successful import of new images."""
    gallery = Gallery.objects.create(name="Test Import Gallery")

    mock_dir = mock.MagicMock()
    mock_dir.exists.return_value = True
    mock_dir.is_dir.return_value = True

    mock_file1 = mock.MagicMock()
    mock_file1.stem = "image1"
    mock_file1.name = "image1.jpg"
    mock_file1.suffix = ".jpg"
    mock_file1.is_file.return_value = True

    mock_file2 = mock.MagicMock()
    mock_file2.stem = "image2"
    mock_file2.name = "image2.png"
    mock_file2.suffix = ".png"
    mock_file2.is_file.return_value = True

    mock_dir.iterdir.return_value = [mock_file1, mock_file2]
    mock_path.return_value = mock_dir

    test_datetime = timezone.make_aware(datetime(2023, 1, 1, 12, 0, 0))
    with mock.patch(
        "gallery2.management.commands.import_images.Command.extract_timestamp"
    ) as mock_extract:
        mock_extract.return_value = test_datetime

        call_command("import_images", "/fake/path", gallery.id)

        assert mock_extract.call_count == 2

    entries = Entry.objects.filter(gallery=gallery)
    assert entries.count() == 2

    basenames = sorted([entry.basename for entry in entries])
    assert basenames == ["image1", "image2"]

    for entry in entries:
        if entry.basename == "image1":
            assert entry.filenames == ["image1.jpg"]
        elif entry.basename == "image2":
            assert entry.filenames == ["image2.png"]

    for entry in entries:
        assert entry.timestamp == test_datetime


@mock.patch("pathlib.Path")
def test_import_images_skip_existing(mock_path, db):
    """Test that existing images are skipped."""
    gallery = Gallery.objects.create(name="Test Skip Gallery")

    Entry.objects.create(
        gallery=gallery,
        basename="existing",
        filenames=["existing.jpg"],
        order=1.0,
        caption="",
    )

    mock_dir = mock.MagicMock()
    mock_dir.exists.return_value = True
    mock_dir.is_dir.return_value = True

    mock_file1 = mock.MagicMock()
    mock_file1.stem = "existing"
    mock_file1.name = "existing.jpg"
    mock_file1.suffix = ".jpg"
    mock_file1.is_file.return_value = True

    mock_file2 = mock.MagicMock()
    mock_file2.stem = "new"
    mock_file2.name = "new.jpg"
    mock_file2.suffix = ".jpg"
    mock_file2.is_file.return_value = True

    mock_dir.iterdir.return_value = [mock_file1, mock_file2]
    mock_path.return_value = mock_dir

    with mock.patch(
        "gallery2.management.commands.import_images.Command.extract_timestamp"
    ) as mock_extract:
        mock_extract.return_value = None
        call_command("import_images", "/fake/path", gallery.id)

    # Check that only one new entry was created (total of 2)
    entries = Entry.objects.filter(gallery=gallery)
    assert entries.count() == 2

    assert Entry.objects.filter(gallery=gallery, basename="new").exists()


@mock.patch("pathlib.Path")
def test_import_images_timestamp_extraction(mock_path, db):
    """Test timestamp extraction from image files."""
    gallery = Gallery.objects.create(name="Test Timestamp Gallery")

    mock_dir = mock.MagicMock()
    mock_dir.exists.return_value = True
    mock_dir.is_dir.return_value = True

    mock_file = mock.MagicMock()
    mock_file.stem = "timestamp_test"
    mock_file.name = "timestamp_test.jpg"
    mock_file.suffix = ".jpg"
    mock_file.is_file.return_value = True

    mock_dir.iterdir.return_value = [mock_file]

    mock_path.return_value = mock_dir

    test_datetime = timezone.make_aware(datetime(2023, 5, 15, 10, 30, 0))

    with mock.patch(
        "gallery2.management.commands.import_images.Command.extract_timestamp"
    ) as mock_extract:
        mock_extract.return_value = test_datetime
        call_command("import_images", "/fake/path", gallery.id)

    entry = Entry.objects.get(gallery=gallery, basename="timestamp_test")
    assert entry.timestamp == test_datetime
    assert "timestamp_test.jpg" in entry.filenames


@mock.patch("pathlib.Path")
def test_import_images_invalid_directory(mock_path, db):
    """Test error handling for invalid directory."""
    gallery = Gallery.objects.create(name="Test Error Gallery")

    mock_dir = mock.MagicMock()
    mock_dir.exists.return_value = False
    mock_path.return_value = mock_dir

    with pytest.raises(CommandError, match="does not exist or is not a directory"):
        call_command("import_images", "/fake/nonexistent/path", gallery.id)


@mock.patch("pathlib.Path")
def test_import_images_invalid_gallery(mock_path, db):
    """Test error handling for invalid gallery ID."""
    non_existent_id = 9999

    with pytest.raises(
        CommandError, match=f"Gallery with ID {non_existent_id} does not exist"
    ):
        call_command("import_images", "/fake/path", non_existent_id)


# Tests for thumbnail view
@mock.patch("gallery2.views.get_thumbnail_extractor")
@mock.patch("pathlib.Path.exists", return_value=True)
@mock.patch("gallery2.views.open")
def test_entry_thumbnail_new(
    mock_open, mock_path_exists, mock_get_extractor, db, client
):
    """Test thumbnail generation when thumbnail doesn't exist."""
    gallery = Gallery.objects.create(
        name="Test Thumbnail Gallery", directory="/fake/gallery/path"
    )
    entry = Entry.objects.create(
        gallery=gallery,
        basename="test_image",
        filenames=["test_image.jpg"],
        order=1.0,
        caption="Test caption",
    )

    mock_extractor = mock.MagicMock()
    mock_extractor.thumbnail_exists.return_value = False
    mock_extractor.get_thumbnail_path.return_value = Path(
        "/fake/thumbnails/path/thumbnail.jpg"
    )
    mock_extractor.extract_thumbnail.return_value = Path(
        "/fake/thumbnails/path/thumbnail.jpg"
    )
    mock_get_extractor.return_value = mock_extractor

    mock_file = mock.MagicMock()
    mock_open.return_value = mock_file

    with mock.patch("gallery2.views.isinstance", return_value=True):
        with mock.patch(
            "gallery2.views.ImageThumbnailExtractor.can_handle", return_value=True
        ):
            response = client.get(
                reverse("gallery2:entry_thumbnail", kwargs={"entry_id": entry.id})
            )

            assert response.status_code == 200
            assert response["Content-Type"] == "image/jpeg"

            mock_get_extractor.assert_called_once_with(
                entry.filenames, gallery.id, entry.id, 800
            )
            mock_extractor.thumbnail_exists.assert_called_once()
            mock_extractor.extract_thumbnail.assert_called_once()
            mock_open.assert_called_once()


@mock.patch("gallery2.views.get_thumbnail_extractor")
@mock.patch("gallery2.views.open")
def test_entry_thumbnail_existing(mock_open, mock_get_extractor, db, client):
    """Test thumbnail serving when thumbnail already exists."""
    gallery = Gallery.objects.create(
        name="Test Existing Thumbnail Gallery", directory="/fake/gallery/path"
    )
    entry = Entry.objects.create(
        gallery=gallery,
        basename="existing_thumb",
        filenames=["existing_thumb.jpg"],
        order=1.0,
        caption="Test caption",
    )

    mock_extractor = mock.MagicMock()
    mock_extractor.thumbnail_exists.return_value = True
    mock_extractor.get_thumbnail_path.return_value = Path(
        "/fake/thumbnails/path/thumbnail.jpg"
    )
    mock_get_extractor.return_value = mock_extractor

    mock_file = mock.MagicMock()
    mock_open.return_value = mock_file

    response = client.get(
        reverse("gallery2:entry_thumbnail", kwargs={"entry_id": entry.id})
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "image/jpeg"

    # Verify the extractor was used correctly and no thumbnail was created (since it already exists)
    mock_get_extractor.assert_called_once_with(
        entry.filenames, gallery.id, entry.id, 800
    )
    mock_extractor.thumbnail_exists.assert_called_once()
    mock_extractor.extract_thumbnail.assert_not_called()
    mock_open.assert_called_once()


@mock.patch("gallery2.views.get_thumbnail_extractor")
def test_entry_thumbnail_no_files(mock_get_extractor, db, client):
    """Test error handling when entry has no files."""
    gallery = Gallery.objects.create(
        name="Test No Files Gallery", directory="/fake/gallery/path"
    )
    entry = Entry.objects.create(
        gallery=gallery,
        basename="no_files",
        filenames=[],  # Empty filenames list
        order=1.0,
        caption="Test caption",
    )

    mock_get_extractor.return_value = None

    response = client.get(
        reverse("gallery2:entry_thumbnail", kwargs={"entry_id": entry.id})
    )

    assert response.status_code == 404
    mock_get_extractor.assert_called_once_with([], gallery.id, entry.id, 800)


@mock.patch("gallery2.views.get_thumbnail_extractor")
@mock.patch("gallery2.views.Path")
def test_entry_thumbnail_file_not_found(mock_path, mock_get_extractor, db, client):
    """Test error handling when original file doesn't exist."""
    gallery = Gallery.objects.create(
        name="Test File Not Found Gallery", directory="/fake/gallery/path"
    )
    entry = Entry.objects.create(
        gallery=gallery,
        basename="missing_file",
        filenames=["missing_file.jpg"],
        order=1.0,
        caption="Test caption",
    )

    mock_extractor = mock.MagicMock()
    mock_extractor.thumbnail_exists.return_value = False
    mock_extractor.extract_thumbnail.side_effect = Http404("Original file not found")
    mock_get_extractor.return_value = mock_extractor

    mock_path_instance = mock.MagicMock()
    mock_path_instance.exists.return_value = False
    mock_path.return_value = mock_path_instance

    with mock.patch("gallery2.views.isinstance", return_value=True):
        with mock.patch(
            "gallery2.views.ImageThumbnailExtractor.can_handle", return_value=True
        ):
            response = client.get(
                reverse("gallery2:entry_thumbnail", kwargs={"entry_id": entry.id})
            )

            assert response.status_code == 404

            mock_get_extractor.assert_called_once_with(
                entry.filenames, gallery.id, entry.id, 800
            )
            mock_extractor.thumbnail_exists.assert_called_once()


@mock.patch("gallery2.views.get_thumbnail_extractor")
@mock.patch("pathlib.Path.exists", return_value=True)
@mock.patch("gallery2.views.open")
def test_entry_thumbnail_with_size(
    mock_open, mock_path_exists, mock_get_extractor, db, client
):
    """Test thumbnail generation with custom size."""
    gallery = Gallery.objects.create(
        name="Test Custom Size Gallery", directory="/fake/gallery/path"
    )
    entry = Entry.objects.create(
        gallery=gallery,
        basename="custom_size",
        filenames=["custom_size.jpg"],
        order=1.0,
        caption="Test caption",
    )

    mock_extractor = mock.MagicMock()
    mock_extractor.thumbnail_exists.return_value = False
    mock_extractor.get_thumbnail_path.return_value = Path(
        "/fake/thumbnails/path/thumbnail.jpg"
    )
    mock_extractor.extract_thumbnail.return_value = Path(
        "/fake/thumbnails/path/thumbnail.jpg"
    )
    mock_get_extractor.return_value = mock_extractor

    mock_file = mock.MagicMock()
    mock_open.return_value = mock_file

    with mock.patch("gallery2.views.isinstance", return_value=True):
        with mock.patch(
            "gallery2.views.ImageThumbnailExtractor.can_handle", return_value=True
        ):
            custom_size = 100
            response = client.get(
                reverse(
                    "gallery2:entry_thumbnail_with_size",
                    kwargs={"entry_id": entry.id, "size": custom_size},
                )
            )

            assert response.status_code == 200
            assert response["Content-Type"] == "image/jpeg"

            mock_get_extractor.assert_called_once_with(
                entry.filenames, gallery.id, entry.id, custom_size
            )
            mock_extractor.thumbnail_exists.assert_called_once()
            mock_extractor.extract_thumbnail.assert_called_once()
            mock_open.assert_called_once()
