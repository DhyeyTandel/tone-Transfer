🎨 AWS Media Processing Pipeline with Color Matching






📌 Overview

A scalable, serverless media processing pipeline built on AWS.
It processes uploaded images, automatically matches the color & lighting of a target image to a reference image, and stores the result back in S3.

🔹 Built with AWS Lambda, S3, API Gateway, Python (Pillow, OpenCV, NumPy, scikit-image).

🛠️ Architecture
flowchart TD
  A[User Uploads Images] -->|S3 Event| B[AWS Lambda]
  B --> C[Color Matching (Histogram Matching)]
  C --> D[Processed Output in S3]
  D --> E[User Fetches via API Gateway]

🚀 Features

⚡ Serverless & Event-Driven – Auto triggers on S3 upload.

🎨 Color & Lighting Matching – Histogram-based adjustment.

☁️ Cloud-Native – Uses AWS managed services.

📈 Scalable – Handles multiple images in parallel.

📂 Project Structure
.
├── lambda_function.py   # Core Lambda with color matching logic
├── requirements.txt     # Python dependencies
├── template.yaml        # (Optional) AWS SAM/CloudFormation template
└── README.md

⚡ Getting Started
1. Clone the Repo
git clone https://github.com/your-username/aws-media-pipeline.git
cd aws-media-pipeline

2. Install Dependencies (for local testing)
pip install -r requirements.txt

3. Deploy Lambda
zip function.zip lambda_function.py requirements.txt
# Upload function.zip to AWS Lambda

4. Setup S3 & Triggers

Create an S3 bucket.

Configure an event notification to trigger Lambda on file upload.

5. (Optional) API Gateway

Create REST API with endpoints:

POST /upload → Upload reference & target images

GET /result/{id} → Fetch processed image

🖼️ Example Usage (Local Test)
from skimage.exposure import match_histograms
from PIL import Image
import numpy as np

ref = np.array(Image.open("reference.jpg"))
target = np.array(Image.open("target.jpg"))

matched = match_histograms(target, ref, channel_axis=-1)
Image.fromarray(matched).save("output.jpg")

✅ Roadmap

 Add video frame-by-frame processing

 Add web UI for uploads

 Batch jobs with Step Functions

👨‍💻 Author

Built by [Dhyey Tandel] – showcasing Cloud + AI image processing skil
