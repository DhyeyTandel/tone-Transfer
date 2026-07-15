"""
AWS Lambda handler entry point for the tone-transfer pipeline.
Triggered by API Gateway HTTP POST request containing image references.
"""

import json
import logging
from typing import Any

import boto3

from tone_transfer.core import match_tone
from tone_transfer.s3_utils import download_image, upload_image

# Set up logging
logger = logging.getLogger("tone_transfer_handler")
logger.setLevel(logging.INFO)
if not logger.handlers:
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(sh)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda entry point triggered by API Gateway proxy integration.

    Expected input event structure:
    {
        "body": "{\"bucket\": \"bucket-name\", \"source_key\": \"path/src.jpg\", \"reference_key\": \"path/ref.jpg\", \"output_key\": \"path/out.jpg\"}"
    }

    Or direct invocation:
    {
        "bucket": "bucket-name",
        "source_key": "path/src.jpg",
        "reference_key": "path/ref.jpg"
    }

    Returns:
        Dict[str, Any]: API Gateway proxy response with 200, 4xx, or 5xx code.
    """
    # 1. Parse request body
    try:
        if "body" in event and isinstance(event["body"], str):
            body = json.loads(event["body"])
        else:
            body = event
    except Exception as e:
        logger.error(f"Failed to parse request JSON body: {e}")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Malformed JSON request: {str(e)}"}),
        }

    # 2. Extract and validate parameters
    if not isinstance(body, dict):
        logger.error("Request body is not a valid JSON object")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Request body must be a JSON object"}),
        }

    bucket = body.get("bucket")
    source_key = body.get("source_key")
    reference_key = body.get("reference_key")
    output_key = body.get("output_key")

    if not bucket or not source_key or not reference_key:
        logger.error("Missing required parameters in request body")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "error": "Missing required parameters. Required fields: 'bucket', 'source_key', 'reference_key'"
                }
            ),
        }

    if not output_key:
        output_key = f"results/{source_key}"

    # 3. Download, process, and upload
    try:
        s3_client = boto3.client("s3")

        # Download source image
        try:
            logger.info(f"Downloading source image: s3://{bucket}/{source_key}")
            source_img = download_image(bucket, source_key, s3_client=s3_client)
        except (OSError, ValueError) as e:
            logger.error(f"Failed to retrieve/decode source image: {e}")
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(
                    {
                        "error": f"Source image '{source_key}' not found or invalid in bucket '{bucket}'"
                    }
                ),
            }

        # Download reference image
        try:
            logger.info(f"Downloading reference image: s3://{bucket}/{reference_key}")
            reference_img = download_image(bucket, reference_key, s3_client=s3_client)
        except (OSError, ValueError) as e:
            logger.error(f"Failed to retrieve/decode reference image: {e}")
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(
                    {
                        "error": f"Reference image '{reference_key}' not found or invalid in bucket '{bucket}'"
                    }
                ),
            }

        # Run tone matching
        logger.info("Executing tone transfer...")
        result_img = match_tone(source_img, reference_img)

        # Upload processed image
        content_type = "image/png" if output_key.lower().endswith(".png") else "image/jpeg"
        logger.info(f"Uploading output image: s3://{bucket}/{output_key}")
        upload_image(bucket, output_key, result_img, content_type=content_type, s3_client=s3_client)

        # Build response payload
        note = (
            f"Generate a presigned GET URL for bucket '{bucket}' and key '{output_key}' "
            "to allow clients to securely retrieve the image."
        )
        response_body = {
            "message": "Tone transfer successful",
            "bucket": bucket,
            "output_key": output_key,
            "presigned_url_instruction": note,
        }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response_body),
        }

    except ValueError as e:
        logger.error(f"Input validation error during processing: {e}")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Processing validation failure: {str(e)}"}),
        }
    except Exception as e:
        logger.error(f"Unexpected pipeline failure: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Internal server error: {str(e)}"}),
        }
