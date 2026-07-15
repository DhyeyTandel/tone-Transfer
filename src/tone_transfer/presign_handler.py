"""
AWS Lambda handler for generating presigned S3 URLs.

Provides two routes via API Gateway:
  - GET /presign?key={key}          → presigned PUT URL for client-side image upload
  - GET /presign-download?key={key} → presigned GET URL for fetching a result image
"""

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger("tone_transfer_presign")
logger.setLevel(logging.INFO)
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(sh)

# Presigned URL expiry: 15 minutes
PRESIGN_EXPIRY_SECONDS = 900

# Resolved at Lambda startup from the environment (injected by SAM template)
BUCKET_NAME = os.environ.get("BUCKET_NAME", "")


def _json_response(status_code: int, body: dict) -> dict[str, Any]:
    """Return an API Gateway proxy response dict."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": json.dumps(body),
    }


def _get_key_from_event(event: dict[str, Any]) -> str | None:
    """Extract the `key` query-string parameter from an API Gateway event."""
    params = event.get("queryStringParameters") or {}
    return params.get("key") or None


def presign_put_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Return a presigned S3 PUT URL that a browser can use to upload an image
    directly to the bucket without AWS credentials.

    Query Parameters:
        key (str): The desired S3 object key for the upload destination.

    Returns:
        200 { upload_url, key, expires_in }
        400 if `key` is missing or `BUCKET_NAME` env var is not set
        500 on unexpected errors
    """
    key = _get_key_from_event(event)
    if not key:
        logger.warning("presign_put_handler called without 'key' query parameter")
        return _json_response(400, {"error": "Missing required query parameter: 'key'"})

    bucket = BUCKET_NAME
    if not bucket:
        logger.error("BUCKET_NAME environment variable is not set")
        return _json_response(500, {"error": "Server misconfiguration: BUCKET_NAME is not set"})

    try:
        s3_client = boto3.client("s3")
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=PRESIGN_EXPIRY_SECONDS,
        )
        logger.info(f"Generated presigned PUT URL for s3://{bucket}/{key}")
        return _json_response(
            200,
            {
                "upload_url": presigned_url,
                "key": key,
                "expires_in": PRESIGN_EXPIRY_SECONDS,
                "method": "PUT",
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate presigned PUT URL: {e}", exc_info=True)
        return _json_response(500, {"error": f"Failed to generate upload URL: {str(e)}"})


def presign_get_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Return a presigned S3 GET URL that a browser can use to download a processed
    result image without AWS credentials.

    Query Parameters:
        key (str): The S3 object key of the result image to download.

    Returns:
        200 { download_url, key, expires_in }
        400 if `key` is missing or `BUCKET_NAME` env var is not set
        500 on unexpected errors
    """
    key = _get_key_from_event(event)
    if not key:
        logger.warning("presign_get_handler called without 'key' query parameter")
        return _json_response(400, {"error": "Missing required query parameter: 'key'"})

    bucket = BUCKET_NAME
    if not bucket:
        logger.error("BUCKET_NAME environment variable is not set")
        return _json_response(500, {"error": "Server misconfiguration: BUCKET_NAME is not set"})

    try:
        s3_client = boto3.client("s3")
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=PRESIGN_EXPIRY_SECONDS,
        )
        logger.info(f"Generated presigned GET URL for s3://{bucket}/{key}")
        return _json_response(
            200,
            {
                "download_url": presigned_url,
                "key": key,
                "expires_in": PRESIGN_EXPIRY_SECONDS,
                "method": "GET",
            },
        )
    except Exception as e:
        logger.error(f"Failed to generate presigned GET URL: {e}", exc_info=True)
        return _json_response(500, {"error": f"Failed to generate download URL: {str(e)}"})


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Unified Lambda entry point for both presign routes.

    Routes are distinguished by the `path` field in the API Gateway event:
      - /presign          → presigned PUT (upload)
      - /presign-download → presigned GET (download)

    Falls back to PUT if the path is unknown (e.g., direct invocation).
    """
    path = event.get("path", "/presign")
    if path == "/presign-download":
        return presign_get_handler(event, context)
    return presign_put_handler(event, context)
