import json
import pytest
from django.urls import reverse
from gallery2.models import Gallery, Entry


@pytest.fixture
def gallery():
    return Gallery.objects.create(name="Test Gallery", directory=".")


@pytest.fixture
def entry(gallery):
    return Entry.objects.create(
        gallery=gallery,
        basename="test_image",
        filenames=["test_image.jpg"],
        order=0.0,
        caption="Original caption",
        timestamp=None,
    )


@pytest.fixture
def edit_caption_url(entry):
    return reverse("gallery2:entry_edit_caption", args=[entry.id])


def test_edit_caption_success(db, client, entry, edit_caption_url):
    new_caption = "Updated caption"
    data = {"caption": new_caption}

    response = client.post(
        edit_caption_url, data=json.dumps(data), content_type="application/json"
    )

    assert response.status_code == 200

    response_data = json.loads(response.content)

    assert response_data["caption"] == new_caption

    entry.refresh_from_db()
    assert entry.caption == new_caption


def test_edit_caption_missing_caption(db, client, entry, edit_caption_url):
    # Data without a caption field
    data = {"other_field": "value"}

    response = client.post(
        edit_caption_url, data=json.dumps(data), content_type="application/json"
    )

    assert response.status_code == 400

    response_data = json.loads(response.content)
    assert response_data["error"] == "Caption field is required"

    # check that the caption was not updated
    entry.refresh_from_db()
    assert entry.caption == "Original caption"


def test_edit_caption_invalid_json(db, client, entry, edit_caption_url):
    """Test that an error is returned when the request body is not valid JSON."""
    response = client.post(
        edit_caption_url, data="not valid json", content_type="application/json"
    )

    assert response.status_code == 400

    response_data = json.loads(response.content)

    assert response_data["error"] == "Invalid JSON data"

    # check that the caption was not updated
    entry.refresh_from_db()
    assert entry.caption == "Original caption"
