"""
Unit tests for core tone transfer logic.
"""

import numpy as np
import pytest

from tone_transfer.core import match_tone


def test_basic_shape_and_dtype():
    """Verify that the shape and data type of the output matches the source image exactly."""
    # Test standard uint8 images
    source_uint8 = np.random.randint(0, 256, (120, 80, 3), dtype=np.uint8)
    ref_uint8 = np.random.randint(0, 256, (200, 150, 3), dtype=np.uint8)

    result = match_tone(source_uint8, ref_uint8)
    assert result.shape == source_uint8.shape
    assert result.dtype == source_uint8.dtype

    # Test float32 normalized image [0, 1]
    source_float32 = np.random.rand(100, 100, 3).astype(np.float32)
    ref_float32 = np.random.rand(120, 120, 3).astype(np.float32)

    result_float = match_tone(source_float32, ref_float32)
    assert result_float.shape == source_float32.shape
    assert result_float.dtype == source_float32.dtype
    assert np.max(result_float) <= 1.01
    assert np.min(result_float) >= 0.0

    # Test RGBA source and RGB reference
    source_rgba = np.random.randint(0, 256, (80, 80, 4), dtype=np.uint8)
    ref_rgb = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

    result_rgba = match_tone(source_rgba, ref_rgb)
    assert result_rgba.shape == source_rgba.shape
    # Check that alpha channel is untouched
    assert np.array_equal(result_rgba[:, :, 3], source_rgba[:, :, 3])


def test_histogram_closeness():
    """Verify that the output tone (mean/std) is closer to the reference than the source was."""
    # Source has cool tones (R is low, B is high)
    source = np.zeros((100, 100, 3), dtype=np.uint8)
    source[:, :, 0] = 50  # Low Red
    source[:, :, 1] = 100  # Med Green
    source[:, :, 2] = 200  # High Blue

    # Reference has warm tones (R is high, B is low)
    reference = np.zeros((150, 150, 3), dtype=np.uint8)
    reference[:, :, 0] = 200  # High Red
    reference[:, :, 1] = 80  # Low Green
    reference[:, :, 2] = 40  # Low Blue

    matched = match_tone(source, reference)

    # Calculate average color vectors
    src_mean = np.mean(source, axis=(0, 1))
    ref_mean = np.mean(reference, axis=(0, 1))
    matched_mean = np.mean(matched, axis=(0, 1))

    # Check L2 distance of average color to reference
    orig_distance = np.linalg.norm(src_mean - ref_mean)
    matched_distance = np.linalg.norm(matched_mean - ref_mean)

    print(f"Original distance to reference: {orig_distance:.3f}")
    print(f"Matched distance to reference: {matched_distance:.3f}")

    assert matched_distance < orig_distance
    # Matched mean should be very close to reference mean
    assert matched_distance < 10.0


def test_grayscale_handling():
    """Verify that grayscale image conversions and combinations work without crashing."""
    # 1. 2D source (grayscale) and 2D reference (grayscale)
    src_2d = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
    ref_2d = np.random.randint(0, 256, (120, 120), dtype=np.uint8)
    result = match_tone(src_2d, ref_2d)
    assert result.shape == src_2d.shape
    assert result.ndim == 2

    # 2. 2D source (grayscale) and 3D reference (RGB)
    ref_rgb = np.random.randint(0, 256, (120, 120, 3), dtype=np.uint8)
    result_gray_ref_rgb = match_tone(src_2d, ref_rgb)
    assert result_gray_ref_rgb.shape == src_2d.shape
    assert result_gray_ref_rgb.ndim == 2

    # 3. 3D source (RGB) and 2D reference (grayscale)
    src_rgb = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    result_rgb_ref_gray = match_tone(src_rgb, ref_2d)
    assert result_rgb_ref_gray.shape == src_rgb.shape
    assert result_rgb_ref_gray.shape[2] == 3

    # 4. 3D source with 1 channel (grayscale) and RGB reference
    src_3d_gray = np.random.randint(0, 256, (100, 100, 1), dtype=np.uint8)
    result_3d_gray = match_tone(src_3d_gray, ref_rgb)
    assert result_3d_gray.shape == src_3d_gray.shape


def test_error_cases():
    """Verify proper errors are raised for invalid inputs."""
    # Empty arrays
    empty_arr = np.array([], dtype=np.uint8)
    valid_arr = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="cannot be empty"):
        match_tone(empty_arr, valid_arr)

    with pytest.raises(ValueError, match="cannot be empty"):
        match_tone(valid_arr, empty_arr)

    # Invalid dimension counts (e.g. 1D or 4D)
    arr_1d = np.random.randint(0, 256, (100,), dtype=np.uint8)
    arr_4d = np.random.randint(0, 256, (10, 10, 10, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="must have 2 or 3 dimensions"):
        match_tone(arr_1d, valid_arr)

    with pytest.raises(ValueError, match="must have 2 or 3 dimensions"):
        match_tone(valid_arr, arr_4d)

    # Invalid type (not numpy ndarray)
    with pytest.raises(TypeError, match="must be numpy ndarrays"):
        match_tone([1, 2, 3], valid_arr)  # type: ignore

    # Unsupported dtypes (e.g. object array)
    obj_arr = np.array([[None, None], [None, None]])
    with pytest.raises(ValueError, match="Unsupported image data type"):
        match_tone(obj_arr, valid_arr)
