import pytest
from gallery2.templatetags.gallery_extras import scale_dimensions


@pytest.mark.parametrize(
    ("width", "height", "max_size", "expected_width", "expected_height", "case_name"),
    [
        # Both dimensions under max_size
        (400, 300, 800, 400, 300, "Both dimensions under max_size"),
        # Width > max_size, height <= max_size
        (1000, 500, 800, 800, 400, "Width > max_size, height <= max_size"),
        # Height > max_size, width <= max_size
        (500, 1000, 800, 400, 800, "Height > max_size, width <= max_size"),
        # Both dimensions > max_size, width needs more scaling
        (
            1600,
            1200,
            800,
            800,
            600,
            "Both dimensions > max_size, width needs more scaling",
        ),
        # Both dimensions > max_size, height needs more scaling
        (
            1200,
            1600,
            800,
            600,
            800,
            "Both dimensions > max_size, height needs more scaling",
        ),
        # Equal dimensions > max_size
        (1000, 1000, 800, 800, 800, "Equal dimensions > max_size"),
        # Edge case - exactly at max_size
        (800, 800, 800, 800, 800, "Edge case - exactly at max_size"),
    ],
)
def test_scale_dimensions(
    width, height, max_size, expected_width, expected_height, case_name
):
    """Test that scale_dimensions correctly scales dimensions while maintaining aspect ratio."""
    result = scale_dimensions(width, height, max_size)
    assert result["width"] == expected_width, f"Failed: {case_name}"
    assert result["height"] == expected_height, f"Failed: {case_name}"


def test_scale_dimensions_none_values():
    """Test that scale_dimensions handles None values correctly."""
    result = scale_dimensions(None, None, 800)
    expected = {"width": "", "height": ""}
    assert result == expected, "Failed: None values"
