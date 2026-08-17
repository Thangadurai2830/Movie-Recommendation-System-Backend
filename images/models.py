from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.validators import FileExtensionValidator
from PIL import Image
import os
from uuid import uuid4

User = get_user_model()


def image_upload_path(instance, filename):
    """Generate upload path for images"""
    ext = filename.split('.')[-1]
    filename = f"{uuid4().hex}.{ext}"
    return os.path.join('images', str(instance.user.id), filename)


def get_default_allowed_formats():
    """Return default allowed image formats"""
    return ['jpg', 'jpeg', 'png', 'gif', 'webp']


class ImageProfile(models.Model):
    """User's image profile settings"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='image_profile')
    max_upload_size = models.IntegerField(default=10485760)  # 10MB in bytes
    allowed_formats = models.JSONField(default=get_default_allowed_formats)
    auto_optimize = models.BooleanField(default=True)
    default_privacy = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public'),
            ('private', 'Private'),
            ('friends', 'Friends Only'),
        ],
        default='private'
    )
    enable_notifications = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Image Profile"


class ImageUpload(models.Model):
    """Main image upload model"""
    PRIVACY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
        ('friends', 'Friends Only'),
    ]
    
    STATUS_CHOICES = [
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='images')
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to=image_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp'])]
    )
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    privacy = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='private')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    file_size = models.IntegerField(default=0)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    format = models.CharField(max_length=10, blank=True)
    tags = models.JSONField(default=list, blank=True)
    views_count = models.IntegerField(default=0)
    likes_count = models.IntegerField(default=0)
    downloads_count = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['privacy', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.title or 'Untitled'} by {self.user.username}"

    def save(self, *args, **kwargs):
        if self.image and not self.width:
            # Extract image metadata
            try:
                with Image.open(self.image) as img:
                    self.width, self.height = img.size
                    self.format = img.format.lower()
                self.file_size = self.image.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def aspect_ratio(self):
        if self.width and self.height:
            return self.width / self.height
        return 1.0

    @property
    def file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)


class ImageMetadata(models.Model):
    """Extended metadata for images"""
    image = models.OneToOneField(ImageUpload, on_delete=models.CASCADE, related_name='metadata')
    exif_data = models.JSONField(default=dict, blank=True)
    color_palette = models.JSONField(default=list, blank=True)  # Dominant colors
    camera_make = models.CharField(max_length=100, blank=True)
    camera_model = models.CharField(max_length=100, blank=True)
    focal_length = models.CharField(max_length=50, blank=True)
    aperture = models.CharField(max_length=50, blank=True)
    iso = models.CharField(max_length=50, blank=True)
    shutter_speed = models.CharField(max_length=50, blank=True)
    gps_latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    gps_longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    location_name = models.CharField(max_length=255, blank=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Metadata for {self.image.title or 'Untitled'}"


class ImageSettings(models.Model):
    """Image appearance and processing settings"""
    FILTER_CHOICES = [
        ('none', 'None'),
        ('vintage', 'Vintage'),
        ('black_white', 'Black & White'),
        ('sepia', 'Sepia'),
        ('vibrant', 'Vibrant'),
        ('cool', 'Cool'),
        ('warm', 'Warm'),
        ('dramatic', 'Dramatic'),
    ]

    image = models.OneToOneField(ImageUpload, on_delete=models.CASCADE, related_name='settings')
    brightness = models.IntegerField(default=0, help_text="-100 to 100")
    contrast = models.IntegerField(default=0, help_text="-100 to 100")
    saturation = models.IntegerField(default=0, help_text="-100 to 100")
    hue = models.IntegerField(default=0, help_text="-180 to 180")
    sharpness = models.IntegerField(default=0, help_text="-100 to 100")
    blur = models.IntegerField(default=0, help_text="0 to 100")
    filter_applied = models.CharField(max_length=20, choices=FILTER_CHOICES, default='none')
    crop_x = models.IntegerField(default=0)
    crop_y = models.IntegerField(default=0)
    crop_width = models.IntegerField(null=True, blank=True)
    crop_height = models.IntegerField(null=True, blank=True)
    rotation = models.IntegerField(default=0, help_text="Degrees: 0, 90, 180, 270")
    flip_horizontal = models.BooleanField(default=False)
    flip_vertical = models.BooleanField(default=False)
    quality = models.IntegerField(default=85, help_text="1 to 100")
    watermark_enabled = models.BooleanField(default=False)
    watermark_text = models.CharField(max_length=100, blank=True)
    watermark_opacity = models.IntegerField(default=50, help_text="0 to 100")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings for {self.image.title or 'Untitled'}"

    @property
    def has_modifications(self):
        """Check if any modifications are applied"""
        return any([
            self.brightness != 0,
            self.contrast != 0,
            self.saturation != 0,
            self.hue != 0,
            self.sharpness != 0,
            self.blur != 0,
            self.filter_applied != 'none',
            self.rotation != 0,
            self.flip_horizontal,
            self.flip_vertical,
            self.crop_width is not None,
        ])


class ImageLike(models.Model):
    """Image likes/favorites"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    image = models.ForeignKey(ImageUpload, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'image']
        indexes = [
            models.Index(fields=['image', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} likes {self.image.title or 'Untitled'}"


class ImageComment(models.Model):
    """Comments on images"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ForeignKey(ImageUpload, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    is_edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['image', '-created_at']),
        ]

    def __str__(self):
        return f"Comment by {self.user.username} on {self.image.title or 'Untitled'}"


class ImageShare(models.Model):
    """Image sharing records"""
    SHARE_TYPE_CHOICES = [
        ('link', 'Direct Link'),
        ('email', 'Email'),
        ('social', 'Social Media'),
        ('embed', 'Embed Code'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ForeignKey(ImageUpload, on_delete=models.CASCADE, related_name='shares')
    share_type = models.CharField(max_length=20, choices=SHARE_TYPE_CHOICES)
    recipient_email = models.EmailField(blank=True)
    share_token = models.UUIDField(default=uuid4, unique=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['share_token']),
            models.Index(fields=['image', '-created_at']),
        ]

    def __str__(self):
        return f"Share {self.image.title or 'Untitled'} via {self.share_type}"


class ImageCollection(models.Model):
    """User-created image collections/albums"""
    PRIVACY_CHOICES = [
        ('public', 'Public'),
        ('private', 'Private'),
        ('friends', 'Friends Only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='image_collections')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    cover_image = models.ForeignKey(ImageUpload, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    images = models.ManyToManyField(ImageUpload, through='ImageCollectionItem', related_name='collections')
    privacy = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='private')
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['privacy', '-updated_at']),
        ]

    def __str__(self):
        return f"{self.name} by {self.user.username}"

    @property
    def image_count(self):
        return self.images.count()


class ImageCollectionItem(models.Model):
    """Through model for image collections"""
    collection = models.ForeignKey(ImageCollection, on_delete=models.CASCADE)
    image = models.ForeignKey(ImageUpload, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['collection', 'image']
        ordering = ['order', 'added_at']

    def __str__(self):
        return f"{self.image.title or 'Untitled'} in {self.collection.name}"
