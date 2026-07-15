"""
S3 Utilities for the tone-transfer pipeline.

Contains helper functions for downloading source/reference images from S3
and uploading the processed results back to S3.
"""

from typing import Any

import boto3
import cv2
import numpy as np


def download_image(bucket: str, key: str, s3_client: Any = None) -> np.ndarray:
    """
    Download an image object from an S3 bucket and load it into a NumPy array.

    Args:
        bucket (str): Name of the S3 bucket.
        key (str): S3 object key (path) of the image.
        s3_client (boto3.resources.factory.s3.Client, optional): Injectable S3 client.

    Returns:
        np.ndarray: The loaded image as a NumPy array (RGB/RGBA or Grayscale).
    """
    if s3_client is None:
        s3_client = boto3.client("s3")

    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        img_bytes = response["Body"].read()
    except Exception as e:
        raise OSError(f"Failed to download s3://{bucket}/{key}: {e}") from e

    arr = np.frombuffer(img_bytes, np.uint8)
    # IMREAD_UNCHANGED retains alpha channel if present
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img_bgr is None:
        raise ValueError(f"Failed to decode image from S3 object: s3://{bucket}/{key}")

    # Convert BGR(A) to RGB(A)
    if img_bgr.ndim == 3:
        if img_bgr.shape[2] == 3:
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        elif img_bgr.shape[2] == 4:
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGRA2RGBA)
        else:
            img_rgb = img_bgr
    else:
        img_rgb = img_bgr

    return img_rgb


def upload_image(
    bucket: str,
    key: str,
    image: np.ndarray,
    content_type: str = "image/jpeg",
    s3_client: Any = None,
) -> None:
    """
    Upload a NumPy image array back to an S3 bucket as an image file.

    Args:
        bucket (str): Name of the S3 bucket.
        key (str): S3 object key (path) for the destination.
        image (np.ndarray): Image array to upload (RGB/RGBA or Grayscale).
        content_type (str): MIME type for the S3 object metadata.
        s3_client (boto3.resources.factory.s3.Client, optional): Injectable S3 client.
    """
    if s3_client is None:
        s3_client = boto3.client("s3")

    # Convert RGB(A) to BGR(A) for encoding
    if image.ndim == 3:
        if image.shape[2] == 3:
            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        elif image.shape[2] == 4:
            image_bgr = cv2.cvtColor(image, cv2.COLOR_RGBA2BGRA)
        else:
            image_bgr = image
    else:
        image_bgr = image

    # Determine standard extension format from content_type
    ext = ".jpg"
    if "png" in content_type.lower():
        ext = ".png"

    success, encoded_img = cv2.imencode(ext, image_bgr)
    if not success:
        raise ValueError(f"Failed to encode image to {ext} format")

    img_bytes = encoded_img.tobytes()

    try:
        s3_client.put_object(Bucket=bucket, Key=key, Body=img_bytes, ContentType=content_type)
    except Exception as e:
        raise OSError(f"Failed to upload s3://{bucket}/{key}: {e}") from e
