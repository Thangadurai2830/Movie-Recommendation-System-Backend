import os
import logging
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont
from io import BytesIO
import numpy as np
from django.core.files.base import ContentFile
from django.conf import settings
from uuid import uuid4

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Advanced image processing utilities"""
    
    @staticmethod
    def create_thumbnail(image_path, size=(300, 300)):
        """Create a thumbnail of the image"""
        try:
            with Image.open(image_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Create thumbnail filename
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                thumbnail_name = f"{base_name}_thumb.jpg"
                thumbnail_dir = os.path.join(os.path.dirname(image_path), 'thumbnails')
                os.makedirs(thumbnail_dir, exist_ok=True)
                thumbnail_path = os.path.join(thumbnail_dir, thumbnail_name)
                
                # Save thumbnail
                img.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
                return thumbnail_path
                
        except Exception as e:
            logger.error(f"Error creating thumbnail: {e}")
            return None
    
    @staticmethod
    def apply_advanced_filter(img, filter_type, intensity=1.0):
        """Apply advanced filters to image"""
        try:
            if filter_type == 'gaussian_blur':
                return img.filter(ImageFilter.GaussianBlur(radius=intensity * 2))
            
            elif filter_type == 'sharpen':
                kernel = ImageFilter.Kernel((3, 3), [-1, -1, -1, -1, 9, -1, -1, -1, -1])
                return img.filter(kernel)
            
            elif filter_type == 'edge_enhance':
                return img.filter(ImageFilter.EDGE_ENHANCE_MORE)
            
            elif filter_type == 'emboss':
                return img.filter(ImageFilter.EMBOSS)
            
            elif filter_type == 'find_edges':
                return img.filter(ImageFilter.FIND_EDGES)
            
            elif filter_type == 'smooth':
                return img.filter(ImageFilter.SMOOTH_MORE)
            
            elif filter_type == 'detail':
                return img.filter(ImageFilter.DETAIL)
            
            elif filter_type == 'contour':
                return img.filter(ImageFilter.CONTOUR)
            
            elif filter_type == 'noise_reduction':
                # Simple noise reduction using median filter
                return img.filter(ImageFilter.MedianFilter(size=3))
            
            return img
            
        except Exception as e:
            logger.error(f"Error applying filter {filter_type}: {e}")
            return img
    
    @staticmethod
    def apply_color_adjustments(img, adjustments):
        """Apply color adjustments to image"""
        try:
            result = img.copy()
            
            # Brightness
            if 'brightness' in adjustments and adjustments['brightness'] != 0:
                enhancer = ImageEnhance.Brightness(result)
                factor = 1 + (adjustments['brightness'] / 100)
                result = enhancer.enhance(max(0.1, min(2.0, factor)))
            
            # Contrast
            if 'contrast' in adjustments and adjustments['contrast'] != 0:
                enhancer = ImageEnhance.Contrast(result)
                factor = 1 + (adjustments['contrast'] / 100)
                result = enhancer.enhance(max(0.1, min(2.0, factor)))
            
            # Saturation
            if 'saturation' in adjustments and adjustments['saturation'] != 0:
                enhancer = ImageEnhance.Color(result)
                factor = 1 + (adjustments['saturation'] / 100)
                result = enhancer.enhance(max(0.0, min(2.0, factor)))
            
            # Sharpness
            if 'sharpness' in adjustments and adjustments['sharpness'] != 0:
                enhancer = ImageEnhance.Sharpness(result)
                factor = 1 + (adjustments['sharpness'] / 100)
                result = enhancer.enhance(max(0.0, min(2.0, factor)))
            
            # Hue adjustment (more complex)
            if 'hue' in adjustments and adjustments['hue'] != 0:
                result = ImageProcessor.adjust_hue(result, adjustments['hue'])
            
            return result
            
        except Exception as e:
            logger.error(f"Error applying color adjustments: {e}")
            return img
    
    @staticmethod
    def adjust_hue(img, hue_shift):
        """Adjust image hue"""
        try:
            # Convert to HSV
            hsv = img.convert('HSV')
            h, s, v = hsv.split()
            
            # Adjust hue
            h_array = np.array(h)
            h_array = (h_array + hue_shift) % 256
            h = Image.fromarray(h_array.astype('uint8'), 'L')
            
            # Merge back
            hsv = Image.merge('HSV', (h, s, v))
            return hsv.convert('RGB')
            
        except Exception as e:
            logger.error(f"Error adjusting hue: {e}")
            return img
    
    @staticmethod
    def apply_artistic_effects(img, effect_type):
        """Apply artistic effects to image"""
        try:
            if effect_type == 'oil_painting':
                # Simulate oil painting effect
                return img.filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.EDGE_ENHANCE)
            
            elif effect_type == 'watercolor':
                # Simulate watercolor effect
                blurred = img.filter(ImageFilter.GaussianBlur(radius=1))
                return ImageEnhance.Color(blurred).enhance(1.3)
            
            elif effect_type == 'pencil_sketch':
                # Convert to grayscale and enhance edges
                gray = img.convert('L')
                edges = gray.filter(ImageFilter.FIND_EDGES)
                return ImageOps.invert(edges).convert('RGB')
            
            elif effect_type == 'cartoon':
                # Cartoon effect using edge detection and color reduction
                edges = img.filter(ImageFilter.FIND_EDGES)
                smooth = img.filter(ImageFilter.SMOOTH_MORE)
                return Image.blend(smooth, edges, 0.2)
            
            elif effect_type == 'pop_art':
                # Pop art effect with high contrast and saturation
                contrast = ImageEnhance.Contrast(img).enhance(1.5)
                return ImageEnhance.Color(contrast).enhance(1.8)
            
            return img
            
        except Exception as e:
            logger.error(f"Error applying artistic effect {effect_type}: {e}")
            return img
    
    @staticmethod
    def crop_image(img, crop_data):
        """Crop image with given coordinates"""
        try:
            x = crop_data.get('x', 0)
            y = crop_data.get('y', 0)
            width = crop_data.get('width', img.width)
            height = crop_data.get('height', img.height)
            
            # Ensure crop coordinates are within image bounds
            x = max(0, min(x, img.width))
            y = max(0, min(y, img.height))
            width = min(width, img.width - x)
            height = min(height, img.height - y)
            
            box = (x, y, x + width, y + height)
            return img.crop(box)
            
        except Exception as e:
            logger.error(f"Error cropping image: {e}")
            return img
    
    @staticmethod
    def resize_image(img, target_size, maintain_aspect=True):
        """Resize image to target size"""
        try:
            if maintain_aspect:
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
                return img
            else:
                return img.resize(target_size, Image.Resampling.LANCZOS)
                
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return img
    
    @staticmethod
    def add_watermark(img, watermark_text, position='bottom-right', opacity=0.5):
        """Add text watermark to image"""
        try:
            # Create a copy to work with
            watermarked = img.copy().convert('RGBA')
            
            # Create a transparent overlay
            overlay = Image.new('RGBA', watermarked.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Try to load a font, fallback to default
            try:
                font_size = max(20, min(watermarked.width, watermarked.height) // 20)
                font = ImageFont.truetype('arial.ttf', font_size)
            except:
                font = ImageFont.load_default()
            
            # Get text size
            bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Calculate position
            margin = 20
            if position == 'bottom-right':
                x = watermarked.width - text_width - margin
                y = watermarked.height - text_height - margin
            elif position == 'bottom-left':
                x = margin
                y = watermarked.height - text_height - margin
            elif position == 'top-right':
                x = watermarked.width - text_width - margin
                y = margin
            elif position == 'top-left':
                x = margin
                y = margin
            elif position == 'center':
                x = (watermarked.width - text_width) // 2
                y = (watermarked.height - text_height) // 2
            else:
                x = margin
                y = margin
            
            # Draw text with semi-transparent background
            alpha = int(255 * opacity)
            draw.rectangle(
                [x - 5, y - 5, x + text_width + 5, y + text_height + 5],
                fill=(0, 0, 0, alpha // 2)
            )
            draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, alpha))
            
            # Composite the overlay onto the image
            watermarked = Image.alpha_composite(watermarked, overlay)
            return watermarked.convert('RGB')
            
        except Exception as e:
            logger.error(f"Error adding watermark: {e}")
            return img
    
    @staticmethod
    def optimize_for_web(img, quality=85, max_width=1920, max_height=1080):
        """Optimize image for web display"""
        try:
            # Resize if too large
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            return img
            
        except Exception as e:
            logger.error(f"Error optimizing image for web: {e}")
            return img
    
    @staticmethod
    def get_image_info(image_path):
        """Get detailed image information"""
        try:
            with Image.open(image_path) as img:
                info = {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size_bytes': os.path.getsize(image_path),
                    'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info,
                }
                
                # Get EXIF data if available
                if hasattr(img, '_getexif') and img._getexif():
                    info['exif'] = dict(img._getexif())
                
                return info
                
        except Exception as e:
            logger.error(f"Error getting image info: {e}")
            return None


class ImageValidator:
    """Image validation utilities"""
    
    ALLOWED_FORMATS = ['JPEG', 'PNG', 'GIF', 'WebP', 'BMP']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_DIMENSIONS = (4096, 4096)
    MIN_DIMENSIONS = (50, 50)
    
    @classmethod
    def validate_image(cls, image_file):
        """Validate uploaded image file"""
        errors = []
        
        try:
            # Check file size
            if hasattr(image_file, 'size') and image_file.size > cls.MAX_FILE_SIZE:
                errors.append(f"File size too large. Maximum allowed: {cls.MAX_FILE_SIZE // (1024*1024)}MB")
            
            # Open and validate image
            with Image.open(image_file) as img:
                # Check format
                if img.format not in cls.ALLOWED_FORMATS:
                    errors.append(f"Unsupported format: {img.format}. Allowed: {', '.join(cls.ALLOWED_FORMATS)}")
                
                # Check dimensions
                if img.width > cls.MAX_DIMENSIONS[0] or img.height > cls.MAX_DIMENSIONS[1]:
                    errors.append(f"Image too large. Maximum: {cls.MAX_DIMENSIONS[0]}x{cls.MAX_DIMENSIONS[1]}")
                
                if img.width < cls.MIN_DIMENSIONS[0] or img.height < cls.MIN_DIMENSIONS[1]:
                    errors.append(f"Image too small. Minimum: {cls.MIN_DIMENSIONS[0]}x{cls.MIN_DIMENSIONS[1]}")
                
                # Check for potential security issues
                if img.mode not in ('RGB', 'RGBA', 'L', 'P'):
                    errors.append(f"Unsupported color mode: {img.mode}")
        
        except Exception as e:
            errors.append(f"Invalid image file: {str(e)}")
        
        return errors
    
    @classmethod
    def is_valid_image(cls, image_file):
        """Check if image file is valid"""
        return len(cls.validate_image(image_file)) == 0