from django.test import Client
from django.urls import reverse
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from django.http import Http404
from unittest import mock
import pytest
import tempfile
import os
import shutil
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from reversion import create_revision
from reversion.models import Version
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from gallery2.models import Gallery, Entry
from gallery2.management.commands.import_images import Command as ImportImagesCommand
from gallery2.utils import timestamp_to_order


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


def test_width_height_attributes(db, client, tmpdir):
    """
    Test that width and height attributes are added to the Entry model and rendered in the template.

    This test:
    1. Creates a test gallery with a 900x600 blue PNG image
    2. Verifies gallery_detail initially has no width/height attributes
    3. Hits the thumbnail endpoint
    4. Verifies the model is updated with width/height
    5. Verifies the rendered gallery_detail includes width/height attributes
    """
    # Create a temporary directory for the test gallery
    # Create a 900x600 blue PNG image
    image_path = os.path.join(tmpdir, "blue_test.png")
    img = Image.new("RGB", (900, 600), color="blue")
    img.save(image_path)

    # Create a gallery with the temporary directory
    gallery = Gallery.objects.create(name="Width Height Test Gallery", directory=tmpdir)

    # Create an entry for the image
    entry = Entry.objects.create(
        gallery=gallery,
        basename="blue_test",
        filenames=["blue_test.png"],
        order=1.0,
        caption="Test image",
    )

    # Verify entry has no width/height initially
    assert entry.width is None
    assert entry.height is None

    # Get the gallery detail page
    response = client.get(reverse("gallery2:gallery_detail", kwargs={"pk": gallery.pk}))
    assert response.status_code == 200

    # Parse the HTML and verify no width/height attributes
    soup = BeautifulSoup(response.content, "html.parser")
    img_tag = soup.find(
        "img",
        {"src": reverse("gallery2:entry_thumbnail", kwargs={"entry_id": entry.id})},
    )
    assert img_tag is not None
    assert "width" not in img_tag.attrs
    assert "height" not in img_tag.attrs

    # Hit the thumbnail endpoint
    thumbnail_response = client.get(
        reverse("gallery2:entry_thumbnail", kwargs={"entry_id": entry.id})
    )
    assert thumbnail_response.status_code == 200

    # Verify the model is updated with width/height
    entry.refresh_from_db()
    assert entry.width == 900
    assert entry.height == 600

    # Get the gallery detail page again
    response = client.get(reverse("gallery2:gallery_detail", kwargs={"pk": gallery.pk}))
    assert response.status_code == 200

    # Parse the HTML and verify width/height attributes are present
    soup = BeautifulSoup(response.content, "html.parser")
    img_tag = soup.find(
        "img",
        {"src": reverse("gallery2:entry_thumbnail", kwargs={"entry_id": entry.id})},
    )
    assert img_tag is not None
    assert "width" in img_tag.attrs
    assert "height" in img_tag.attrs

    # Verify the width is scaled to 800 (or less if original is smaller)
    expected_width = min(800, entry.width)
    expected_height = (
        int(entry.height * (expected_width / entry.width))
        if entry.width > 800
        else entry.height
    )

    assert int(img_tag["width"]) == expected_width
    assert int(img_tag["height"]) == expected_height


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


@mock.patch("pathlib.Path")
def test_import_images_timestamp_ordering(mock_path, db):
    """Test that images are ordered by timestamp."""
    gallery = Gallery.objects.create(name="Test Timestamp Ordering Gallery")

    mock_dir = mock.MagicMock()
    mock_dir.exists.return_value = True
    mock_dir.is_dir.return_value = True

    # Create three mock image files
    mock_file1 = mock.MagicMock()
    mock_file1.stem = "image1"
    mock_file1.name = "image1.jpg"
    mock_file1.suffix = ".jpg"
    mock_file1.is_file.return_value = True

    mock_file2 = mock.MagicMock()
    mock_file2.stem = "image2"
    mock_file2.name = "image2.jpg"
    mock_file2.suffix = ".jpg"
    mock_file2.is_file.return_value = True

    mock_file3 = mock.MagicMock()
    mock_file3.stem = "image3"
    mock_file3.name = "image3.jpg"
    mock_file3.suffix = ".jpg"
    mock_file3.is_file.return_value = True

    mock_dir.iterdir.return_value = [mock_file1, mock_file2, mock_file3]
    mock_path.return_value = mock_dir

    # Create three different timestamps
    timestamp1 = timezone.make_aware(datetime(2023, 1, 1, 12, 0, 0))  # Earliest
    timestamp2 = timezone.make_aware(datetime(2023, 1, 2, 12, 0, 0))  # Middle
    timestamp3 = timezone.make_aware(datetime(2023, 1, 3, 12, 0, 0))  # Latest

    # Mock extract_timestamp to return different timestamps for each file
    with mock.patch(
        "gallery2.management.commands.import_images.Command.extract_timestamp"
    ) as mock_extract:
        # Return timestamps in non-chronological order to test sorting
        mock_extract.side_effect = [timestamp2, timestamp3, timestamp1]

        # Call the command with a starting order of 10.0
        call_command("import_images", "/fake/path", gallery.id, "--order", "10.0")

    # Get entries sorted by basename
    entries = Entry.objects.filter(gallery=gallery).order_by("basename")
    assert entries.count() == 3

    # Create a mapping of basename to entry for easier testing
    entry_map = {entry.basename: entry for entry in entries}

    # Verify timestamps are set correctly
    assert entry_map["image1"].timestamp == timestamp2
    assert entry_map["image2"].timestamp == timestamp3
    assert entry_map["image3"].timestamp == timestamp1

    # Verify order values are assigned based on timestamp in the format yyyymmdd.hhmmss
    # image3 has timestamp 2023-01-01 12:00:00, so it should have order=20230101.12 + 10.0
    # image1 has timestamp 2023-01-02 12:00:00, so it should have order=20230102.12 + 10.0
    # image2 has timestamp 2023-01-03 12:00:00, so it should have order=20230103.12 + 10.0

    # Calculate expected order values using the timestamp_to_order function
    command = ImportImagesCommand()
    expected_order3 = timestamp_to_order(timestamp1) + 10.0  # Earliest timestamp
    expected_order1 = timestamp_to_order(timestamp2) + 10.0  # Middle timestamp
    expected_order2 = timestamp_to_order(timestamp3) + 10.0  # Latest timestamp

    assert entry_map["image3"].order == expected_order3  # Earliest timestamp
    assert entry_map["image1"].order == expected_order1  # Middle timestamp
    assert entry_map["image2"].order == expected_order2  # Latest timestamp


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
    mock_extractor.extract_thumbnail.return_value = (
        Path("/fake/thumbnails/path/thumbnail.jpg"),
        800,  # width
        600,  # height
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
    mock_extractor.extract_thumbnail.return_value = (
        Path("/fake/thumbnails/path/thumbnail.jpg"),
        400,  # width
        300,  # height
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


@mock.patch("gallery2.views.get_thumbnail_extractor")
@mock.patch("pathlib.Path.exists", return_value=True)
@mock.patch("gallery2.views.open")
def test_entry_thumbnail_hidden(
    mock_open, mock_path_exists, mock_get_extractor, db, client
):
    """Test thumbnail generation with hidden entry (should use size 100)."""
    gallery = Gallery.objects.create(
        name="Test Hidden Entry Gallery", directory="/fake/gallery/path"
    )
    entry = Entry.objects.create(
        gallery=gallery,
        basename="hidden_entry",
        filenames=["hidden_entry.jpg"],
        order=1.0,
        caption="Test caption",
        hidden=True,  # This entry is hidden
    )

    mock_extractor = mock.MagicMock()
    mock_extractor.thumbnail_exists.return_value = False
    mock_extractor.get_thumbnail_path.return_value = Path(
        "/fake/thumbnails/path/thumbnail.jpg"
    )
    mock_extractor.extract_thumbnail.return_value = (
        Path("/fake/thumbnails/path/thumbnail.jpg"),
        400,  # width
        300,  # height
    )
    mock_get_extractor.return_value = mock_extractor

    mock_file = mock.MagicMock()
    mock_open.return_value = mock_file

    with mock.patch("gallery2.views.isinstance", return_value=True):
        with mock.patch(
            "gallery2.views.ImageThumbnailExtractor.can_handle", return_value=True
        ):
            # Use the default size URL (should be overridden to 100 for hidden entries)
            response = client.get(
                reverse(
                    "gallery2:entry_thumbnail",
                    kwargs={"entry_id": entry.id},
                )
            )

            assert response.status_code == 200
            assert response["Content-Type"] == "image/jpeg"

            # Verify that size 100 was used for the hidden entry
            mock_get_extractor.assert_called_once_with(
                entry.filenames, gallery.id, entry.id, 100
            )
            mock_extractor.thumbnail_exists.assert_called_once()
            mock_extractor.extract_thumbnail.assert_called_once()
            mock_open.assert_called_once()


def test_entry_caption_version_history(db):
    gallery = Gallery.objects.create(name="Version History Test Gallery")

    caption_a = "A"
    with create_revision():
        entry = Entry.objects.create(
            gallery=gallery,
            basename="version_test",
            filenames=["version_test.jpg"],
            order=1.0,
            caption=caption_a,
        )

    # Update the entry with caption value B
    caption_b = "B"
    with create_revision():
        entry.caption = caption_b
        entry.save()

    entry_from_db = Entry.objects.get(pk=entry.pk)
    assert entry_from_db.caption == caption_b

    # Verify that value A is accessible through the version history
    versions = Version.objects.get_for_object(entry)
    assert versions.count() == 2

    # The most recent version should have caption B
    assert versions[0].field_dict["caption"] == caption_b
    # The older version should have caption A
    assert versions[1].field_dict["caption"] == caption_a


def test_timestamp_to_order_conversion():
    """Test the conversion of timestamps to order values."""
    command = ImportImagesCommand()

    # Test with None timestamp (should return infinity)
    assert timestamp_to_order(None) == float("inf")

    # Test with midnight UTC (should have 0.0 fraction)
    dt_midnight = datetime(2023, 1, 1, 0, 0, 0, tzinfo=dt_timezone.utc)
    expected_midnight = 20230101.0
    assert timestamp_to_order(dt_midnight) == expected_midnight

    # Test with noon UTC (should have 0.12 fraction)
    dt_noon = datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)
    expected_noon = 20230101.12
    assert timestamp_to_order(dt_noon) == expected_noon

    # Test with end of day UTC (should have 0.235959 fraction)
    dt_end_of_day = datetime(2023, 1, 1, 23, 59, 59, tzinfo=dt_timezone.utc)
    expected_end_of_day = 20230101.235959
    assert timestamp_to_order(dt_end_of_day) == expected_end_of_day

    # Test with non-UTC timezone (should be converted to UTC)
    # Create a timezone 5 hours ahead of UTC
    tz_plus_5 = dt_timezone(
        dt_timezone.utc.utcoffset(None) + timezone.timedelta(hours=5)
    )
    dt_non_utc = datetime(2023, 1, 1, 5, 0, 0, tzinfo=tz_plus_5)  # This is midnight UTC
    expected_non_utc = 20230101.0
    assert timestamp_to_order(dt_non_utc) == expected_non_utc

    # Test with a different date and time
    dt_different_date = datetime(2025, 5, 15, 6, 30, 0, tzinfo=dt_timezone.utc)
    expected_different_date = 20250515.063
    assert timestamp_to_order(dt_different_date) == expected_different_date
