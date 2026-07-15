# Tone Transfer

A serverless AWS image processing pipeline that transfers the lighting and color tone from a **reference image** onto a **source image** using per-channel histogram matching in the LAB color space. Images never touch the Lambda execution environment directly — clients upload and download via short-lived presigned S3 URLs, so the pipeline stays stateless and scales to zero when idle. The stack is entirely defined in `template.yaml` and deployed with [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/).

---

## Request Flow

```
Browser / CLI
  │
  │ 1. GET  /presign?key=inputs/source.jpg
  │         ← { upload_url, expires_in: 900 }
  │
  │ 2. PUT  <upload_url>  (raw image bytes, no AWS credentials needed)
  │         ← 200 from S3
  │
  │    (repeat steps 1–2 for the reference image)
  │
  │ 3. POST /transfer  { bucket, source_key, reference_key }
  │         ← { output_key }           (Lambda runs histogram matching)
  │
  │ 4. GET  /presign-download?key=<output_key>
  │         ← { download_url, expires_in: 900 }
  │
  │ 5. GET  <download_url>  → save matched image locally
  ▼
S3 Bucket  (tone-transfer-images-<account>-<region>)
  ├── inputs/        ← source & reference uploads
  └── results/       ← tone-matched outputs
```

---

## Directory Structure

```text
.
├── Makefile                        # Developer shortcuts (install, test, lint, deploy, local)
├── README.md
├── requirements.txt                # Python deps (OpenCV, scikit-image, boto3, moto, ruff …)
├── ruff.toml                       # Linter / formatter config
├── template.yaml                   # AWS SAM template (S3 bucket, Lambdas, API Gateway, IAM)
├── docker-compose.yml              # LocalStack for local S3 mocking
├── env.local.json                  # Lambda env vars for `sam local start-api`
├── scripts/
│   └── demo.py                     # End-to-end CLI demo (upload → transfer → download)
├── src/
│   └── tone_transfer/
│       ├── __init__.py
│       ├── core.py                 # Pure histogram-matching logic (no AWS deps)
│       ├── handler.py              # Lambda: POST /transfer
│       ├── presign_handler.py      # Lambda: GET /presign, GET /presign-download
│       └── s3_utils.py             # S3 download/upload helpers
└── tests/
    ├── test_core.py
    ├── test_handler.py
    └── test_presign_handler.py
```

---

## Setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/DhyeyTandel/Tone_Transfer.git
cd Tone_Transfer

# 2. Install all Python dependencies into a local virtualenv
make install
```

---

## Running Tests

```bash
make test          # runs pytest with PYTHONPATH=src
make lint          # runs ruff check + ruff format --check
```

Or directly:

```bash
PYTHONPATH=src .venv/bin/pytest tests/ -v
.venv/bin/ruff check src/ tests/
```

---

## Local Development (LocalStack + SAM)

Run the full Lambda stack locally without AWS credentials:

```bash
# Requires: Docker, AWS CLI, AWS SAM CLI
make local
```

This does three things in sequence:

1. Starts **LocalStack** via `docker compose up -d` and waits for S3 to be ready.
2. Creates a local `s3://tone-transfer-local` bucket inside LocalStack.
3. Runs `sam local start-api --env-vars env.local.json` on port **3000**.

Test it:

```bash
curl "http://localhost:3000/presign?key=inputs/test.jpg"
```

To tear down LocalStack:

```bash
make localstack-down
```

---

## Deployment

### First deploy (interactive — creates `samconfig.toml`)

```bash
make deploy-guided
```

Follow the prompts to set your AWS region, stack name, and S3 deployment bucket.
SAM will print the API base URL and image bucket name as stack outputs when done.

### Subsequent deploys

```bash
make deploy        # reads samconfig.toml automatically
```

---

## End-to-End Demo

After deploying, verify the full pipeline with a single command:

```bash
make demo \
  API=https://<api-id>.execute-api.<region>.amazonaws.com/prod \
  SRC=path/to/source.jpg \
  REF=path/to/reference.jpg
```

This runs [`scripts/demo.py`](scripts/demo.py) which:

1. Generates a presigned PUT URL for the source image and uploads it.
2. Generates a presigned PUT URL for the reference image and uploads it.
3. Calls `POST /transfer` to run tone matching.
4. Generates a presigned GET URL for the result.
5. Downloads the matched image and saves it as `matched.jpg`.

---

## API Contract

### `GET /presign`

Generate a **presigned PUT URL** for uploading a source or reference image directly from the browser to S3.

**Query parameters**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `key` | ✅ | Desired S3 object key, e.g. `inputs/source.jpg` |

**Response `200`**

```json
{
  "upload_url": "https://bucket.s3.amazonaws.com/inputs/source.jpg?X-Amz-Signature=…",
  "key": "inputs/source.jpg",
  "expires_in": 900,
  "method": "PUT"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| `400` | `key` query parameter missing |
| `500` | Server misconfiguration or unexpected boto3 error |

---

### `GET /presign-download`

Generate a **presigned GET URL** for downloading a processed result image.

**Query parameters**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `key` | ✅ | S3 key of the result, e.g. `results/inputs/source.jpg` |

**Response `200`**

```json
{
  "download_url": "https://bucket.s3.amazonaws.com/results/inputs/source.jpg?X-Amz-Signature=…",
  "key": "results/inputs/source.jpg",
  "expires_in": 900,
  "method": "GET"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| `400` | `key` query parameter missing |
| `500` | Server misconfiguration or unexpected boto3 error |

---

### `POST /transfer`

Trigger the tone transfer pipeline. Downloads source and reference images from S3, runs per-channel histogram matching, and uploads the result.

**Request body (JSON)**

```json
{
  "bucket":        "tone-transfer-images-123456789-us-east-1",
  "source_key":    "inputs/source.jpg",
  "reference_key": "inputs/reference.jpg",
  "output_key":    "results/inputs/source.jpg"
}
```

`output_key` is optional; defaults to `results/{source_key}`.

**Response `200`**

```json
{
  "message":                  "Tone transfer successful",
  "bucket":                   "tone-transfer-images-123456789-us-east-1",
  "output_key":               "results/inputs/source.jpg",
  "presigned_url_instruction": "Generate a presigned GET URL for bucket '…' and key '…' …"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| `400` | Missing `bucket`, `source_key`, or `reference_key`; malformed JSON |
| `404` | Source or reference image not found in the specified bucket |
| `500` | Image decode/encode failure or unexpected pipeline error |

---

## CI

GitHub Actions runs on every push and pull request:

- **Lint** — `ruff check` + `ruff format --check`
- **Test** — `pytest tests/ -v` on Python 3.11 and 3.12

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).