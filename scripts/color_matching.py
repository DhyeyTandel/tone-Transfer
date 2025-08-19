import cv2
import numpy as np
from PIL import Image
import io
import base64

def rgb_to_lab(image):
    """Convert RGB image to LAB color space"""
    return cv2.cvtColor(image, cv2.COLOR_RGB2LAB)

def lab_to_rgb(image):
    """Convert LAB image back to RGB color space"""
    return cv2.cvtColor(image, cv2.COLOR_LAB2RGB)

def match_histograms_lab(source, reference):
    """
    Perform histogram matching in LAB color space
    
    Args:
        source: Source image (numpy array) to be adjusted
        reference: Reference image (numpy array) to match
    
    Returns:
        Matched image in RGB format
    """
    # Convert both images to LAB color space
    source_lab = rgb_to_lab(source)
    reference_lab = rgb_to_lab(reference)
    
    # Split into L, A, B channels
    source_l, source_a, source_b = cv2.split(source_lab)
    ref_l, ref_a, ref_b = cv2.split(reference_lab)
    
    # Match histogram for each channel
    matched_l = match_histogram_channel(source_l, ref_l)
    matched_a = match_histogram_channel(source_a, ref_a)
    matched_b = match_histogram_channel(source_b, ref_b)
    
    # Merge channels back
    matched_lab = cv2.merge([matched_l, matched_a, matched_b])
    
    # Convert back to RGB
    matched_rgb = lab_to_rgb(matched_lab)
    
    return matched_rgb

def match_histogram_channel(source, reference):
    """
    Match histogram of a single channel
    
    Args:
        source: Source channel (2D numpy array)
        reference: Reference channel (2D numpy array)
    
    Returns:
        Histogram matched channel
    """
    # Calculate histograms
    source_hist, _ = np.histogram(source.flatten(), 256, [0, 256])
    reference_hist, _ = np.histogram(reference.flatten(), 256, [0, 256])
    
    # Calculate cumulative distribution functions
    source_cdf = source_hist.cumsum()
    reference_cdf = reference_hist.cumsum()
    
    # Normalize CDFs
    source_cdf = source_cdf / source_cdf[-1]
    reference_cdf = reference_cdf / reference_cdf[-1]
    
    # Create lookup table
    lookup_table = np.zeros(256, dtype=np.uint8)
    
    for i in range(256):
        # Find the closest match in reference CDF
        closest_match = np.argmin(np.abs(reference_cdf - source_cdf[i]))
        lookup_table[i] = closest_match
    
    # Apply lookup table to source image
    matched = cv2.LUT(source, lookup_table)
    
    return matched

def process_images_from_base64(reference_b64, target_b64):
    """
    Process base64 encoded images and return color-matched result
    
    Args:
        reference_b64: Base64 encoded reference image
        target_b64: Base64 encoded target image
    
    Returns:
        Base64 encoded processed image
    """
    try:
        # Decode base64 images
        reference_data = base64.b64decode(reference_b64)
        target_data = base64.b64decode(target_b64)
        
        # Convert to PIL Images
        reference_pil = Image.open(io.BytesIO(reference_data)).convert('RGB')
        target_pil = Image.open(io.BytesIO(target_data)).convert('RGB')
        
        # Convert to numpy arrays
        reference_np = np.array(reference_pil)
        target_np = np.array(target_pil)
        
        # Perform color matching
        matched_image = match_histograms_lab(target_np, reference_np)
        
        # Convert back to PIL Image
        matched_pil = Image.fromarray(matched_image.astype(np.uint8))
        
        # Convert to base64
        buffer = io.BytesIO()
        matched_pil.save(buffer, format='JPEG', quality=95)
        matched_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return matched_b64
        
    except Exception as e:
        raise Exception(f"Image processing failed: {str(e)}")

# Test the algorithm with sample processing
if __name__ == "__main__":
    print("Color matching algorithm loaded successfully!")
    print("Functions available:")
    print("- match_histograms_lab(): Main color matching function")
    print("- process_images_from_base64(): Process base64 encoded images")
    print("- rgb_to_lab() / lab_to_rgb(): Color space conversion utilities")
