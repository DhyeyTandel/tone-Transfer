"""
Unit tests for the presign Lambda handler.

boto3's generate_presigned_url is mocked so no real AWS credentials are
needed and no HTTP traffic is made.
"""

import json
from unittest.mock import MagicMock, patch

import tone_transfer.presign_handler as presign_module

# ── constants ─────────────────────────────────────────────────────────────────

FAKE_BUCKET = "fake-bucket"
FAKE_PUT_URL = (
    "https://fake-bucket.s3.amazonaws.com/inputs/photo.jpg?X-Amz-Signature=abc&X-Amz-Expires=900"
)
FAKE_GET_URL = (
    "https://fake-bucket.s3.amazonaws.com/results/photo.jpg?X-Amz-Signature=xyz&X-Amz-Expires=900"
)


def _make_apigw_event(path: str, key: str | None = None) -> dict:
    """Build a minimal API Gateway proxy event."""
    return {
        "path": path,
        "queryStringParameters": {"key": key} if key else {},
    }


# ── presign PUT (upload) ──────────────────────────────────────────────────────


class TestPresignPut:
    @patch.object(presign_module, "BUCKET_NAME", FAKE_BUCKET)
    @patch("tone_transfer.presign_handler.boto3")
    def test_returns_200_with_upload_url(self, mock_boto3):
        """Happy path: valid key returns 200 with a well-formed upload URL."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = FAKE_PUT_URL

        event = _make_apigw_event("/presign", key="inputs/photo.jpg")
        response = presign_module.presign_put_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["upload_url"] == FAKE_PUT_URL
        assert body["key"] == "inputs/photo.jpg"
        assert body["expires_in"] == 900
        assert body["method"] == "PUT"

        mock_s3.generate_presigned_url.assert_called_once_with(
            ClientMethod="put_object",
            Params={"Bucket": FAKE_BUCKET, "Key": "inputs/photo.jpg"},
            ExpiresIn=900,
        )

    @patch.object(presign_module, "BUCKET_NAME", FAKE_BUCKET)
    @patch("tone_transfer.presign_handler.boto3")
    def test_url_is_well_formed_string(self, mock_boto3):
        """The returned URL must be a non-empty https:// string with a query string."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = FAKE_PUT_URL

        event = _make_apigw_event("/presign", key="src/my-image.jpg")
        body = json.loads(presign_module.presign_put_handler(event, None)["body"])

        url = body["upload_url"]
        assert isinstance(url, str) and len(url) > 0
        assert url.startswith("https://")
        assert "?" in url  # must contain query-string params (signature etc.)

    @patch.object(presign_module, "BUCKET_NAME", FAKE_BUCKET)
    @patch("tone_transfer.presign_handler.boto3")
    def test_missing_key_returns_400(self, mock_boto3):
        """A request without a `key` parameter must return 400."""
        event = _make_apigw_event("/presign", key=None)
        response = presign_module.presign_put_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        assert "key" in body["error"].lower()

    @patch.object(presign_module, "BUCKET_NAME", "")
    @patch("tone_transfer.presign_handler.boto3")
    def test_missing_bucket_env_returns_500(self, _mock_boto3):
        """If BUCKET_NAME is empty/unset, a 500 must be returned."""
        event = _make_apigw_event("/presign", key="any.jpg")
        response = presign_module.presign_put_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "BUCKET_NAME" in body["error"] or "misconfiguration" in body["error"].lower()

    @patch.object(presign_module, "BUCKET_NAME", FAKE_BUCKET)
    @patch("tone_transfer.presign_handler.boto3")
    def test_boto3_error_returns_500(self, mock_boto3):
        """If boto3 raises an unexpected exception, a 500 must be returned."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.generate_presigned_url.side_effect = RuntimeError("boto3 gone wrong")

        event = _make_apigw_event("/presign", key="src.jpg")
        response = presign_module.presign_put_handler(event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "error" in body


# ── presign GET (download) ────────────────────────────────────────────────────


class TestPresignGet:
    @patch.object(presign_module, "BUCKET_NAME", FAKE_BUCKET)
    @patch("tone_transfer.presign_handler.boto3")
    def test_returns_200_with_download_url(self, mock_boto3):
        """Happy path: valid key returns 200 with a well-formed download URL."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = FAKE_GET_URL

        event = _make_apigw_event("/presign-download", key="results/photo.jpg")
        response = presign_module.presign_get_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["download_url"] == FAKE_GET_URL
        assert body["key"] == "results/photo.jpg"
        assert body["expires_in"] == 900
        assert body["method"] == "GET"

        mock_s3.generate_presigned_url.assert_called_once_with(
            ClientMethod="get_object",
            Params={"Bucket": FAKE_BUCKET, "Key": "results/photo.jpg"},
            ExpiresIn=900,
        )

    @patch.object(presign_module, "BUCKET_NAME", FAKE_BUCKET)
    @patch("tone_transfer.presign_handler.boto3")
    def test_missing_key_returns_400(self, mock_boto3):
        """A request without a `key` parameter must return 400."""
        event = _make_apigw_event("/presign-download", key=None)
        response = presign_module.presign_get_handler(event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body


# ── unified lambda_handler routing ───────────────────────────────────────────


class TestLambdaHandlerRouting:
    @patch.object(presign_module, "BUCKET_NAME", FAKE_BUCKET)
    @patch("tone_transfer.presign_handler.boto3")
    def test_routes_presign_to_put(self, mock_boto3):
        """/presign path is routed to the PUT presigner."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = FAKE_PUT_URL

        event = _make_apigw_event("/presign", key="img.jpg")
        response = presign_module.lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "upload_url" in body

    @patch.object(presign_module, "BUCKET_NAME", FAKE_BUCKET)
    @patch("tone_transfer.presign_handler.boto3")
    def test_routes_presign_download_to_get(self, mock_boto3):
        """/presign-download path is routed to the GET presigner."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = FAKE_GET_URL

        event = _make_apigw_event("/presign-download", key="results/img.jpg")
        response = presign_module.lambda_handler(event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "download_url" in body

    @patch.object(presign_module, "BUCKET_NAME", FAKE_BUCKET)
    @patch("tone_transfer.presign_handler.boto3")
    def test_cors_headers_present(self, mock_boto3):
        """CORS headers must be included in every response."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = FAKE_PUT_URL

        event = _make_apigw_event("/presign", key="img.jpg")
        response = presign_module.lambda_handler(event, None)

        headers = response.get("headers", {})
        assert "Access-Control-Allow-Origin" in headers
        assert headers["Access-Control-Allow-Origin"] == "*"
