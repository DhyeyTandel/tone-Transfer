"""
Core image processing and tone transfer logic.

This module contains pure image processing functions to transfer the color
and lighting tone from a reference image onto a source image.
It contains no AWS-specific or S3 dependencies.
"""

import cv2
import numpy as np
from skimage.exposure import match_histograms as skimage_match_histograms


def _to_uint8_internal(img: np.ndarray) -> tuple[np.ndarray, bool]:
    """
    Convert an image to uint8 internally, tracking if it was a normalized float.
    """
    if not np.issubdtype(img.dtype, np.number):
        raise ValueError(f"Unsupported image data type: {img.dtype}")

    was_normalized_float = False

    if img.dtype == np.uint8:
        return img, was_normalized_float

    if np.issubdtype(img.dtype, np.floating):
        max_val = np.max(img)
        # Assume it's normalized in [0, 1] if max value is <= 1.01
        if max_val <= 1.01:
            was_normalized_float = True
            scaled = np.clip(img * 255.0, 0, 255)
            return scaled.astype(np.uint8), was_normalized_float
        else:
            return np.clip(img, 0, 255).astype(np.uint8), was_normalized_float

    elif np.issubdtype(img.dtype, np.integer):
        return np.clip(img, 0, 255).astype(np.uint8), was_normalized_float

    else:
        raise ValueError(f"Unsupported image data type: {img.dtype}")


def match_tone(source_img: np.ndarray, reference_img: np.ndarray) -> np.ndarray:
    """
    Perform per-channel histogram matching to transfer the color and lighting
    tone of the reference image onto the source image.

    Supports RGB, RGBA, and Grayscale images. Leaves the source resolution
    and alpha channel (if present) untouched.

    Args:
        source_img (np.ndarray): The source image to modify.
        reference_img (np.ndarray): The reference image whose tone to copy.

    Returns:
        np.ndarray: The modified source image matching the reference tone,
                    retaining the original shape and data type of source_img.

    Raises:
        ValueError: If inputs are empty, have unsupported shapes/dimensions,
                    or mismatched channel counts that cannot be reconciled.
        TypeError: If inputs are not numpy arrays.

    Example:
        >>> import numpy as np
        >>> source = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        >>> reference = np.random.randint(50, 150, (150, 150, 3), dtype=np.uint8)
        >>> matched = match_tone(source, reference)
        >>> matched.shape == source.shape
        True
        >>> matched.dtype == source.dtype
        True
    """
    # 1. Type validation
    if not isinstance(source_img, np.ndarray) or not isinstance(reference_img, np.ndarray):
        raise TypeError("Images must be numpy ndarrays")

    # 2. Empty array checks
    if source_img.size == 0 or reference_img.size == 0:
        raise ValueError("Images cannot be empty")

    # 3. Dimension checks
    if source_img.ndim not in (2, 3) or reference_img.ndim not in (2, 3):
        raise ValueError("Images must have 2 or 3 dimensions")

    # Save original properties to restore them at the end
    orig_dtype = source_img.dtype
    orig_shape = source_img.shape

    # 4. Convert inputs to uint8 internally
    src_uint8, src_was_float = _to_uint8_internal(source_img)
    ref_uint8, _ = _to_uint8_internal(reference_img)

    # 5. Extract alpha channel from source if present
    has_alpha = False
    src_alpha = None
    if src_uint8.ndim == 3 and src_uint8.shape[2] == 4:
        has_alpha = True
        src_alpha = src_uint8[:, :, 3]
        src_rgb = src_uint8[:, :, :3]
    else:
        src_rgb = src_uint8

    # 6. Extract/strip alpha channel from reference if present
    if ref_uint8.ndim == 3 and ref_uint8.shape[2] == 4:
        ref_rgb = ref_uint8[:, :, :3]
    else:
        ref_rgb = ref_uint8

    # Helper function to query the channel count
    def get_channels(img: np.ndarray) -> int:
        if img.ndim == 2:
            return 1
        if img.ndim == 3:
            if img.shape[2] in (1, 3):
                return img.shape[2]
        raise ValueError(f"Unsupported image shape: {img.shape}")

    src_ch = get_channels(src_rgb)
    ref_ch = get_channels(ref_rgb)

    # 7. Reconcile channel differences
    # Convert reference to match source channel count
    if src_ch == 3 and ref_ch == 1:
        # Convert reference from grayscale to RGB
        ref_gray_2d = ref_rgb if ref_rgb.ndim == 2 else ref_rgb[:, :, 0]
        ref_aligned = cv2.cvtColor(ref_gray_2d, cv2.COLOR_GRAY2RGB)
        src_aligned = src_rgb
    elif src_ch == 1 and ref_ch == 3:
        # Convert reference from RGB to grayscale
        ref_aligned = cv2.cvtColor(ref_rgb, cv2.COLOR_RGB2GRAY)
        if src_rgb.ndim == 3:
            ref_aligned = np.expand_dims(ref_aligned, axis=-1)
        src_aligned = src_rgb
    else:
        # No channel count differences to reconcile (1 vs 1 or 3 vs 3)
        # Ensure dimensional consistency (both 2D or both 3D)
        src_aligned = src_rgb
        if src_rgb.ndim == 2 and ref_rgb.ndim == 3:
            ref_aligned = ref_rgb[:, :, 0]
        elif src_rgb.ndim == 3 and ref_rgb.ndim == 2:
            ref_aligned = np.expand_dims(ref_rgb, axis=-1)
        else:
            ref_aligned = ref_rgb

    # 8. Apply histogram matching
    if src_aligned.ndim == 2:
        matched_rgb = skimage_match_histograms(src_aligned, ref_aligned, channel_axis=None)
    else:
        matched_rgb = skimage_match_histograms(src_aligned, ref_aligned, channel_axis=-1)

    # 9. Re-integrate alpha channel if present
    if has_alpha:
        matched_output = np.dstack((matched_rgb, src_alpha))
    else:
        matched_output = matched_rgb

    # 10. Restore original format/dtype
    if src_was_float:
        restored = matched_output.astype(orig_dtype) / 255.0
    else:
        restored = matched_output.astype(orig_dtype)

    # Ensure shape is exactly restored (useful for 3D 1-channel images)
    if restored.shape != orig_shape:
        restored = restored.reshape(orig_shape)

    return restored


def rgb_to_lab(image: np.ndarray) -> np.ndarray:
    """
    Convert an RGB image to the LAB color space.

    Args:
        image (np.ndarray): Input RGB image array.

    Returns:
        np.ndarray: Converted image in LAB color space.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Image must be RGB (3 channels)")
    img_uint8, _ = _to_uint8_internal(image)
    return cv2.cvtColor(img_uint8, cv2.COLOR_RGB2LAB)


def lab_to_rgb(image: np.ndarray) -> np.ndarray:
    """
    Convert a LAB image back to the RGB color space.

    Args:
        image (np.ndarray): Input LAB image array.

    Returns:
        np.ndarray: Converted image in RGB color space.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Image must be LAB (3 channels)")
    img_uint8, _ = _to_uint8_internal(image)
    return cv2.cvtColor(img_uint8, cv2.COLOR_LAB2RGB)


def match_histograms(source: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """
    Transfer the tone/color distribution of the reference image onto the source
    image using histogram matching in LAB color space.

    Args:
        source (np.ndarray): The source/target image to be modified.
        reference (np.ndarray): The reference image whose tone/color will be matched.

    Returns:
        np.ndarray: The modified source image with reference tones applied.
    """
    return match_tone(source, reference)
