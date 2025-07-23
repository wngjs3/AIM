import os
import base64
import hashlib
from PIL import Image

# Inactivity detection constants
INACTIVITY_GRID_SIZE = 3  # 3x3 grid for image comparison
INACTIVITY_CENTER_CELL = 4  # Center cell (0-indexed, so 4 is the 5th cell)
INACTIVITY_SIMILARITY_THRESHOLD = 0.95  # Similarity threshold for image comparison


def extract_center_cell_base64(image_path):
    """
    Extract the center cell from an image divided into 3x3 grid and return as base64.

    Args:
        image_path (str): Path to the image file

    Returns:
        str: Base64 encoded center cell image, or None if error
    """
    try:
        # Load image with PIL
        with Image.open(image_path) as img:
            # Convert to RGB if needed
            if img.mode != "RGB":
                img = img.convert("RGB")

            width, height = img.size

            # Calculate grid cell dimensions
            cell_width = width // INACTIVITY_GRID_SIZE
            cell_height = height // INACTIVITY_GRID_SIZE

            # Calculate center cell position (cell 4 in 0-indexed 3x3 grid)
            # Grid layout: 0 1 2
            #              3 4 5
            #              6 7 8
            center_row = INACTIVITY_CENTER_CELL // INACTIVITY_GRID_SIZE  # row 1
            center_col = INACTIVITY_CENTER_CELL % INACTIVITY_GRID_SIZE  # col 1

            # Calculate crop coordinates
            left = center_col * cell_width
            top = center_row * cell_height
            right = left + cell_width
            bottom = top + cell_height

            # Extract center cell
            center_cell = img.crop((left, top, right, bottom))

            # Convert to base64
            import io

            buffer = io.BytesIO()
            center_cell.save(buffer, format="JPEG", quality=85)
            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

            return encoded

    except Exception as e:
        print(f"[INACTIVITY] Error extracting center cell from {image_path}: {e}")
        return None


def calculate_hash_similarity(data1, data2):
    """
    Calculate similarity between two base64 strings using hash comparison.

    Args:
        data1 (str): First base64 string
        data2 (str): Second base64 string

    Returns:
        float: Similarity score (1.0 if identical, 0.0 if completely different)
    """
    try:
        if not data1 or not data2:
            return 0.0

        # Direct string comparison for exact match
        if data1 == data2:
            return 1.0

        # Calculate MD5 hashes for quick comparison
        hash1 = hashlib.md5(data1.encode()).hexdigest()
        hash2 = hashlib.md5(data2.encode()).hexdigest()

        if hash1 == hash2:
            return 1.0

        # For approximate similarity, compare chunks of the base64 string
        # This is a simple approach - divide string into chunks and count matches
        chunk_size = 100
        chunks1 = [data1[i : i + chunk_size] for i in range(0, len(data1), chunk_size)]
        chunks2 = [data2[i : i + chunk_size] for i in range(0, len(data2), chunk_size)]

        # Compare chunks
        min_chunks = min(len(chunks1), len(chunks2))
        if min_chunks == 0:
            return 0.0

        matching_chunks = sum(1 for i in range(min_chunks) if chunks1[i] == chunks2[i])
        similarity = matching_chunks / min_chunks

        return similarity

    except Exception as e:
        print(f"[INACTIVITY] Error calculating hash similarity: {e}")
        return 0.0


def compare_images_for_inactivity(current_image_path, reference_image_path):
    """
    Compare two images to detect inactivity by comparing their center cells.

    Args:
        current_image_path (str): Path to current image
        reference_image_path (str): Path to reference image (5 minutes ago)

    Returns:
        tuple: (is_inactive, similarity_score)
               is_inactive (bool): True if images are too similar (inactive)
               similarity_score (float): Similarity score between 0 and 1
    """
    try:
        # Check if files exist
        if not os.path.exists(current_image_path):
            print(f"[INACTIVITY] Current image not found: {current_image_path}")
            return False, 0.0

        if not os.path.exists(reference_image_path):
            print(f"[INACTIVITY] Reference image not found: {reference_image_path}")
            return False, 0.0

        # Extract center cells as base64
        current_center = extract_center_cell_base64(current_image_path)
        reference_center = extract_center_cell_base64(reference_image_path)

        if current_center is None or reference_center is None:
            print("[INACTIVITY] Failed to extract center cells")
            return False, 0.0

        # Calculate similarity
        similarity = calculate_hash_similarity(current_center, reference_center)

        # Determine if inactive (too similar)
        is_inactive = similarity >= INACTIVITY_SIMILARITY_THRESHOLD

        print(
            f"[INACTIVITY] Similarity: {similarity:.3f}, Threshold: {INACTIVITY_SIMILARITY_THRESHOLD}, Inactive: {is_inactive}"
        )

        return is_inactive, similarity

    except Exception as e:
        print(f"[INACTIVITY] Error comparing images: {e}")
        return False, 0.0
