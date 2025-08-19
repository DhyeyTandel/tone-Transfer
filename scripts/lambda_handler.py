import json
import boto3
from color_matching import process_images_from_base64
import base64
import io
from PIL import Image
import numpy as np

# Initialize S3 client
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """
    AWS Lambda handler for image color matching
    
    Expected event structure:
    {
        "reference_image_key": "path/to/reference.jpg",
        "target_image_key": "path/to/target.jpg",
        "bucket_name": "your-s3-bucket",
        "output_key": "path/to/output.jpg"
    }
    """
    
    try:
        # Extract parameters from event
        bucket_name = event.get('bucket_name')
        reference_key = event.get('reference_image_key')
        target_key = event.get('target_image_key')
        output_key = event.get('output_key')
        
        if not all([bucket_name, reference_key, target_key, output_key]):
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameters',
                    'required': ['bucket_name', 'reference_image_key', 'target_image_key', 'output_key']
                })
            }
        
        # Download images from S3
        print(f"[v0] Downloading reference image: {reference_key}")
        reference_obj = s3_client.get_object(Bucket=bucket_name, Key=reference_key)
        reference_data = reference_obj['Body'].read()
        
        print(f"[v0] Downloading target image: {target_key}")
        target_obj = s3_client.get_object(Bucket=bucket_name, Key=target_key)
        target_data = target_obj['Body'].read()
        
        # Convert to base64 for processing
        reference_b64 = base64.b64encode(reference_data).decode('utf-8')
        target_b64 = base64.b64encode(target_data).decode('utf-8')
        
        print("[v0] Starting color matching process")
        # Process images using color matching algorithm
        processed_b64 = process_images_from_base64(reference_b64, target_b64)
        
        # Convert processed image back to bytes
        processed_data = base64.b64decode(processed_b64)
        
        # Upload processed image to S3
        print(f"[v0] Uploading processed image: {output_key}")
        s3_client.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=processed_data,
            ContentType='image/jpeg'
        )
        
        # Generate presigned URL for the processed image (optional)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': output_key},
            ExpiresIn=3600  # 1 hour
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Image processing completed successfully',
                'output_key': output_key,
                'presigned_url': presigned_url,
                'processing_details': {
                    'algorithm': 'LAB histogram matching',
                    'reference_image': reference_key,
                    'target_image': target_key
                }
            })
        }
        
    except Exception as e:
        print(f"[v0] Error during processing: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Image processing failed',
                'details': str(e)
            })
        }

def handle_api_gateway_event(event, context):
    """
    Alternative handler for API Gateway integration
    Expects multipart form data or JSON with base64 images
    """
    
    try:
        # Parse the request body
        if event.get('isBase64Encoded'):
            body = base64.b64decode(event['body']).decode('utf-8')
        else:
            body = event.get('body', '{}')
        
        request_data = json.loads(body)
        
        # Extract base64 images from request
        reference_b64 = request_data.get('reference_image')
        target_b64 = request_data.get('target_image')
        
        if not reference_b64 or not target_b64:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Both reference_image and target_image are required as base64 strings'
                })
            }
        
        print("[v0] Processing images via API Gateway")
        # Process the images
        processed_b64 = process_images_from_base64(reference_b64, target_b64)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'processed_image': processed_b64,
                'message': 'Color matching completed successfully'
            })
        }
        
    except Exception as e:
        print(f"[v0] API Gateway error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Processing failed',
                'details': str(e)
            })
        }
