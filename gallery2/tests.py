from django.test import Client
from django.urls import reverse
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
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
        filename="image1.jpg",
        order=2.0,
        caption="This is **bold** text",
    )
    entry2 = Entry.objects.create(
        gallery=gallery,
        filename="image2.jpg",
        order=1.0,
        caption="This is *italic* text",
    )
    entry3 = Entry.objects.create(
        gallery=gallery,
        filename="image3.jpg",
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

    assert entry1.filename in response.text
    assert entry2.filename in response.text
    assert entry3.filename in response.text

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

    filenames = sorted([entry.filename for entry in entries])
    assert filenames == ["image1.jpg", "image2.png"]

    for entry in entries:
        assert entry.timestamp == test_datetime


@mock.patch("pathlib.Path")
def test_import_images_skip_existing(mock_path, db):
    """Test that existing images are skipped."""
    gallery = Gallery.objects.create(name="Test Skip Gallery")

    Entry.objects.create(
        gallery=gallery, filename="existing.jpg", order=1.0, caption=""
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

    assert Entry.objects.filter(gallery=gallery, filename="new.jpg").exists()


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

    entry = Entry.objects.get(gallery=gallery, filename="timestamp_test.jpg")
    assert entry.timestamp == test_datetime


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
