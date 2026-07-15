#!/usr/bin/env python3
"""
scripts/demo.py — end-to-end tone-transfer demo.

Verifies a full deploy by:
  1. Getting a presigned PUT URL for the source image  → GET /presign
  2. Uploading the source image directly to S3         → PUT <url>
  3. Getting a presigned PUT URL for the reference     → GET /presign
  4. Uploading the reference image directly to S3      → PUT <url>
  5. Triggering tone transfer                          → POST /transfer
  6. Getting a presigned GET URL for the result        → GET /presign-download
  7. Downloading and saving the result image locally   → GET <url>

Usage:
    python scripts/demo.py \\
        --api-base https://<id>.execute-api.<region>.amazonaws.com/prod \\
        --source   path/to/source.jpg \\
        --reference path/to/reference.jpg \\
        [--output   matched.jpg]

For local testing against sam local start-api (port 3000):
    python scripts/demo.py \\
        --api-base http://localhost:3000 \\
        --source   path/to/source.jpg \\
        --reference path/to/reference.jpg
"""

import argparse
import sys
import os
import time
import pathlib
import requests

# ─────────────────────────────────────────────────────────────────────────────

def _step(n: int, text: str) -> None:
    print(f"\n  [{n}/7] {text}")


def _check(resp: requests.Response, label: str) -> dict:
    """Raise with a clear message on non-2xx responses."""
    if not resp.ok:
        print(f"  ❌  {label} failed — HTTP {resp.status_code}")
        try:
            body = resp.json()
            print(f"       {body}")
        except Exception:
            print(f"       {resp.text[:500]}")
        sys.exit(1)
    return resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else {}


def presign_upload(api_base: str, key: str) -> str:
    """Call GET /presign and return the presigned PUT URL."""
    resp = requests.get(f"{api_base}/presign", params={"key": key}, timeout=15)
    data = _check(resp, f"GET /presign?key={key}")
    url = data.get("upload_url")
    if not url:
        print(f"  ❌  No upload_url in response: {data}")
        sys.exit(1)
    return url


def upload_to_s3(presigned_url: str, file_path: pathlib.Path) -> None:
    """PUT the raw file bytes directly to the presigned S3 URL."""
    content_type = (
        "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
    )
    with open(file_path, "rb") as fh:
        resp = requests.put(
            presigned_url,
            data=fh,
            headers={"Content-Type": content_type},
            timeout=60,
        )
    if not resp.ok:
        print(f"  ❌  S3 upload failed — HTTP {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)


def trigger_transfer(api_base: str, bucket: str, source_key: str, reference_key: str, output_key: str) -> str:
    """POST /transfer and return the result S3 key."""
    payload = {
        "bucket": bucket,
        "source_key": source_key,
        "reference_key": reference_key,
        "output_key": output_key,
    }
    resp = requests.post(f"{api_base}/transfer", json=payload, timeout=120)
    data = _check(resp, "POST /transfer")
    result_key = data.get("output_key")
    if not result_key:
        print(f"  ❌  No output_key in response: {data}")
        sys.exit(1)
    return result_key


def presign_download(api_base: str, key: str) -> str:
    """Call GET /presign-download and return the presigned GET URL."""
    resp = requests.get(f"{api_base}/presign-download", params={"key": key}, timeout=15)
    data = _check(resp, f"GET /presign-download?key={key}")
    url = data.get("download_url")
    if not url:
        print(f"  ❌  No download_url in response: {data}")
        sys.exit(1)
    return url


def download_result(presigned_url: str, output_path: pathlib.Path) -> None:
    """Download the result image from the presigned GET URL and save to disk."""
    resp = requests.get(presigned_url, timeout=60, stream=True)
    if not resp.ok:
        print(f"  ❌  Result download failed — HTTP {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            fh.write(chunk)


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end demo of the tone-transfer API pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--api-base",   required=True,  help="Base URL of the deployed API (no trailing slash)")
    parser.add_argument("--source",     required=True,  help="Local path to the source image")
    parser.add_argument("--reference",  required=True,  help="Local path to the reference image")
    parser.add_argument("--output",     default="matched.jpg", help="Path to save the matched result image")
    parser.add_argument("--bucket",     default="",     help="S3 bucket name (auto-detected from presign response if empty)")
    args = parser.parse_args()

    api_base    = args.api_base.rstrip("/")
    source_path = pathlib.Path(args.source)
    ref_path    = pathlib.Path(args.reference)
    out_path    = pathlib.Path(args.output)

    if not source_path.exists():
        print(f"❌  Source image not found: {source_path}")
        sys.exit(1)
    if not ref_path.exists():
        print(f"❌  Reference image not found: {ref_path}")
        sys.exit(1)

    # Derive S3 keys from file names
    ts          = int(time.time())
    source_key  = f"inputs/{ts}-{source_path.name}"
    ref_key     = f"inputs/{ts}-{ref_path.name}"
    output_key  = f"results/{ts}-{source_path.name}"

    print(f"\n🖼  Tone Transfer — end-to-end demo")
    print(f"   API base  : {api_base}")
    print(f"   Source    : {source_path}  →  s3://{source_key}")
    print(f"   Reference : {ref_path}  →  s3://{ref_key}")
    print(f"   Output    : {out_path}  ←  s3://{output_key}")

    # 1. Presign source upload
    _step(1, f"Getting presigned PUT URL for source: {source_key}")
    src_upload_url = presign_upload(api_base, source_key)
    print(f"     ✅  Got upload URL")

    # 2. Upload source
    _step(2, f"Uploading source image to S3 …")
    upload_to_s3(src_upload_url, source_path)
    print(f"     ✅  Source uploaded ({source_path.stat().st_size // 1024} KB)")

    # 3. Presign reference upload
    _step(3, f"Getting presigned PUT URL for reference: {ref_key}")
    ref_upload_url = presign_upload(api_base, ref_key)
    print(f"     ✅  Got upload URL")

    # 4. Upload reference
    _step(4, f"Uploading reference image to S3 …")
    upload_to_s3(ref_upload_url, ref_path)
    print(f"     ✅  Reference uploaded ({ref_path.stat().st_size // 1024} KB)")

    # 5. Trigger tone transfer
    _step(5, "Calling POST /transfer …")
    # Derive bucket from the upload URL hostname if not supplied
    bucket = args.bucket
    if not bucket:
        host = src_upload_url.split("//")[-1].split(".s3.")[0].split("/")[0]
        bucket = host if host else "unknown-bucket"
    result_key = trigger_transfer(api_base, bucket, source_key, ref_key, output_key)
    print(f"     ✅  Transfer complete — result key: {result_key}")

    # 6. Presign download
    _step(6, f"Getting presigned GET URL for result: {result_key}")
    dl_url = presign_download(api_base, result_key)
    print(f"     ✅  Got download URL")

    # 7. Download result
    _step(7, f"Downloading result image → {out_path}")
    download_result(dl_url, out_path)
    print(f"     ✅  Saved to {out_path} ({out_path.stat().st_size // 1024} KB)")

    print(f"\n🎉  Done!  Open {out_path} to inspect the tone-matched image.\n")


if __name__ == "__main__":
    main()
