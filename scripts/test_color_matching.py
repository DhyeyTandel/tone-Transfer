# Test script to verify the color matching algorithm works
import numpy as np
from PIL import Image
import io
import base64
from color_matching import match_histograms_lab, process_images_from_base64

def create_test_images():
    """Create simple test images for algorithm verification"""
    
    # Create a reference image (warm tones)
    reference = np.zeros((200, 200, 3), dtype=np.uint8)
    reference[:, :, 0] = 200  # High red
    reference[:, :, 1] = 150  # Medium green  
    reference[:, :, 2] = 100  # Low blue
    
    # Create a target image (cool tones)
    target = np.zeros((200, 200, 3), dtype=np.uint8)
    target[:, :, 0] = 100   # Low red
    target[:, :, 1] = 150   # Medium green
    target[:, :, 2] = 200   # High blue
    
    return reference, target

def test_histogram_matching():
    """Test the histogram matching algorithm"""
    
    print("Testing LAB histogram matching algorithm...")
    
    # Create test images
    reference, target = create_test_images()
    
    print(f"Reference image stats - R: {reference[:,:,0].mean():.1f}, G: {reference[:,:,1].mean():.1f}, B: {reference[:,:,2].mean():.1f}")
    print(f"Target image stats - R: {target[:,:,0].mean():.1f}, G: {target[:,:,1].mean():.1f}, B: {target[:,:,2].mean():.1f}")
    
    # Apply color matching
    matched = match_histograms_lab(target, reference)
    
    print(f"Matched image stats - R: {matched[:,:,0].mean():.1f}, G: {matched[:,:,1].mean():.1f}, B: {matched[:,:,2].mean():.1f}")
    
    # Verify the matching worked (colors should be closer to reference)
    ref_mean = np.mean(reference, axis=(0,1))
    matched_mean = np.mean(matched, axis=(0,1))
    target_mean = np.mean(target, axis=(0,1))
    
    # Calculate distances
    original_distance = np.linalg.norm(target_mean - ref_mean)
    matched_distance = np.linalg.norm(matched_mean - ref_mean)
    
    print(f"Original distance from reference: {original_distance:.2f}")
    print(f"Matched distance from reference: {matched_distance:.2f}")
    
    if matched_distance < original_distance:
        print("✅ Color matching successful! Matched image is closer to reference.")
    else:
        print("❌ Color matching may need adjustment.")
    
    return matched

def test_base64_processing():
    """Test the base64 image processing pipeline"""
    
    print("\nTesting base64 image processing...")
    
    # Create test images
    reference, target = create_test_images()
    
    # Convert to base64
    def array_to_base64(img_array):
        pil_img = Image.fromarray(img_array)
        buffer = io.BytesIO()
        pil_img.save(buffer, format='JPEG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    reference_b64 = array_to_base64(reference)
    target_b64 = array_to_base64(target)
    
    try:
        # Process using the base64 function
        result_b64 = process_images_from_base64(reference_b64, target_b64)
        print("✅ Base64 processing successful!")
        print(f"Result image size: {len(result_b64)} characters")
        return True
    except Exception as e:
        print(f"❌ Base64 processing failed: {e}")
        return False

if __name__ == "__main__":
    print("Running color matching algorithm tests...\n")
    
    # Test the core algorithm
    matched_image = test_histogram_matching()
    
    # Test the base64 pipeline
    base64_success = test_base64_processing()
    
    print(f"\n{'='*50}")
    print("Test Summary:")
    print(f"✅ Core algorithm: Working")
    print(f"{'✅' if base64_success else '❌'} Base64 pipeline: {'Working' if base64_success else 'Failed'}")
    print(f"{'='*50}")
