from fastapi import APIRouter, UploadFile, File, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image
import io

router = APIRouter()
app = FastAPI()

def compress_image_to_buffer(image: Image.Image, max_size_kb: int, quality: int = 95) -> io.BytesIO:
    """Compress image to a buffer with target sizes."""
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    return buffer

def resize_image_if_needed(image: Image.Image, max_dimension: int = 2000) -> Image.Image:
    """Resize image if it exceeds maximum dimensions while maintaining aspect ratio."""
    if max(image.size) > max_dimension:
        ratio = max_dimension / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        return image.resize(new_size, Image.Resampling.LANCZOS)
    return image

@router.post("/compress/image")
async def compress_image(
    file: UploadFile = File(...),
    max_size_kb: int = 400,
    min_quality: int = 20,
    max_dimension: int = 2000
):
    try:
        # Read and validate input image
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if needed (handles PNG with transparency)
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1])
            image = background
        
        # Initial resize if image is too large
        image = resize_image_if_needed(image, max_dimension)
        
        # Try different quality levels
        quality = 95
        while quality >= min_quality:
            buffer = compress_image_to_buffer(image, max_size_kb, quality)
            if len(buffer.getvalue()) <= max_size_kb * 1024:
                # Create filename for the compressed image
                original_filename = file.filename
                filename_without_ext = original_filename.rsplit('.', 1)[0]
                compressed_filename = f"{filename_without_ext}_compressed.jpg"
                
                # Return StreamingResponse with download headers
                return StreamingResponse(
                    buffer, 
                    media_type="image/jpeg",
                    headers={
                        "Content-Disposition": f'attachment; filename="{compressed_filename}"'
                    }
                )
            
            quality -= 5
            
            # If quality reduction isn't enough, resize the image
            if quality < min_quality:
                if max(image.size) <= 500:  # Prevent images becoming too small
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot compress image below {max_size_kb}KB while maintaining acceptable quality"
                    )
                
                # Reduce size by 20% and reset quality
                new_size = tuple(int(dim * 0.8) for dim in image.size)
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                quality = 95

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Include the router in the FastAPI app
app.include_router(router)





