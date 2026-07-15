"""
Integration tests for the Lambda handler using Moto for S3 mocking.
"""

import json

import boto3
import cv2
import numpy as np
from moto import mock_aws

from tone_transfer.handler import lambda_handler


def generate_valid_image_bytes(shape=(10, 10, 3), color=(255, 0, 0)) -> bytes:
    """Helper to generate valid JPEG image bytes using OpenCV."""
    img = np.zeros(shape, dtype=np.uint8)
    img[:] = color
    success, encoded = cv2.imencode(".jpg", img)
    if not success:
        raise ValueError("Failed to encode image to JPEG")
    return encoded.tobytes()


@mock_aws
def test_lambda_handler_success():
    """Verify that lambda_handler runs successfully with valid S3 inputs."""
    s3_client = boto3.client("s3", region_name="us-east-1")
    bucket_name = "my-test-bucket"
    s3_client.create_bucket(Bucket=bucket_name)

    # Seed mock S3 with valid source and reference images
    source_bytes = generate_valid_image_bytes(shape=(20, 20, 3), color=(0, 0, 255))  # Blue
    ref_bytes = generate_valid_image_bytes(shape=(15, 15, 3), color=(255, 0, 0))  # Red

    s3_client.put_object(Bucket=bucket_name, Key="inputs/source.jpg", Body=source_bytes)
    s3_client.put_object(Bucket=bucket_name, Key="inputs/reference.jpg", Body=ref_bytes)

    # Call handler with a mock API Gateway event
    event = {
        "body": json.dumps(
            {
                "bucket": bucket_name,
                "source_key": "inputs/source.jpg",
                "reference_key": "inputs/reference.jpg",
                "output_key": "outputs/result.jpg",
            }
        )
    }

    response = lambda_handler(event, None)

    assert response["statusCode"] == 200
    assert "Content-Type" in response["headers"]

    body = json.loads(response["body"])
    assert body["bucket"] == bucket_name
    assert body["output_key"] == "outputs/result.jpg"
    assert "presigned_url_instruction" in body

    # Assert that output file was written back to mock S3
    s3_response = s3_client.get_object(Bucket=bucket_name, Key="outputs/result.jpg")
    output_bytes = s3_response["Body"].read()

    # Verify that the written object is a valid decodable image
    arr = np.frombuffer(output_bytes, np.uint8)
    decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape == (20, 20, 3)  # Matches source resolution


@mock_aws
def test_lambda_handler_missing_params():
    """Verify that a request with missing parameters returns a 400 error."""
    event = {
        "body": json.dumps(
            {
                "bucket": "some-bucket",
                "source_key": "source.jpg",
                # reference_key is missing
            }
        )
    }

    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert "Missing required parameters" in body["error"]


@mock_aws
def test_lambda_handler_malformed_json():
    """Verify that a request with malformed JSON body returns a 400 error."""
    event = {"body": "{invalid-json}"}

    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert "Malformed JSON request" in body["error"]


@mock_aws
def test_lambda_handler_image_not_found():
    """Verify that a 404 is returned when S3 objects do not exist."""
    s3_client = boto3.client("s3", region_name="us-east-1")
    bucket_name = "empty-bucket"
    s3_client.create_bucket(Bucket=bucket_name)

    # Request refers to key not in the bucket
    event = {
        "body": json.dumps(
            {
                "bucket": bucket_name,
                "source_key": "does-not-exist.jpg",
                "reference_key": "some-reference.jpg",
            }
        )
    }

    response = lambda_handler(event, None)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert "error" in body
    assert "not found or invalid" in body["error"]


@mock_aws
def test_lambda_handler_default_output_key():
    """Verify that output_key defaults to results/source_key if not specified."""
    s3_client = boto3.client("s3", region_name="us-east-1")
    bucket_name = "default-key-bucket"
    s3_client.create_bucket(Bucket=bucket_name)

    source_bytes = generate_valid_image_bytes()
    ref_bytes = generate_valid_image_bytes()

    s3_client.put_object(Bucket=bucket_name, Key="src.jpg", Body=source_bytes)
    s3_client.put_object(Bucket=bucket_name, Key="ref.jpg", Body=ref_bytes)

    event = {
        "body": json.dumps(
            {"bucket": bucket_name, "source_key": "src.jpg", "reference_key": "ref.jpg"}
        )
    }

    response = lambda_handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])

    # Default is results/source_key
    assert body["output_key"] == "results/src.jpg"

    # Verify the object exists at that location
    s3_response = s3_client.get_object(Bucket=bucket_name, Key="results/src.jpg")
    assert s3_response["ContentLength"] > 0
