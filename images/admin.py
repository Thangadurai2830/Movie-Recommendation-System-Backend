from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    ImageProfile, ImageUpload, ImageMetadata, ImageSettings,
    ImageLike, ImageComment, ImageShare, ImageCollection, ImageCollectionItem
)


@admin.register(ImageProfile)
class ImageProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'max_upload_size_mb', 'default_privacy', 'auto_optimize', 'enable_notifications', 'created_at']
    list_filter = ['default_privacy', 'auto_optimize', 'enable_notifications', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']
    
    def max_upload_size_mb(self, obj):
        return f"{obj.max_upload_size / (1024 * 1024):.1f} MB"
    max_upload_size_mb.short_description = 'Max Upload Size'


class ImageMetadataInline(admin.StackedInline):
    model = ImageMetadata
    extra = 0
    readonly_fields = ['created_at']


class ImageSettingsInline(admin.StackedInline):
    model = ImageSettings
    extra = 0
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ImageUpload)
class ImageUploadAdmin(admin.ModelAdmin):
    list_display = [
        'title_display', 'user', 'status', 'privacy', 'file_size_mb', 
        'dimensions', 'views_count', 'likes_count', 'created_at', 'image_preview'
    ]
    list_filter = ['status', 'privacy', 'format', 'is_featured', 'created_at']
    search_fields = ['title', 'description', 'user__username', 'tags']
    readonly_fields = [
        'id', 'file_size', 'width', 'height', 'format', 'views_count', 
        'likes_count', 'downloads_count', 'created_at', 'updated_at', 'image_preview'
    ]
    inlines = [ImageMetadataInline, ImageSettingsInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'title', 'description', 'image', 'image_preview')
        }),
        ('Settings', {
            'fields': ('privacy', 'status', 'tags', 'is_featured')
        }),
        ('Metadata', {
            'fields': ('file_size', 'width', 'height', 'format'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('views_count', 'likes_count', 'downloads_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def title_display(self, obj):
        return obj.title or 'Untitled'
    title_display.short_description = 'Title'
    
    def file_size_mb(self, obj):
        return f"{obj.file_size_mb} MB"
    file_size_mb.short_description = 'File Size'
    
    def dimensions(self, obj):
        return f"{obj.width} × {obj.height}"
    dimensions.short_description = 'Dimensions'
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;" />',
                obj.image.url
            )
        return 'No image'
    image_preview.short_description = 'Preview'


@admin.register(ImageMetadata)
class ImageMetadataAdmin(admin.ModelAdmin):
    list_display = ['image', 'camera_make', 'camera_model', 'location_name', 'taken_at', 'created_at']
    list_filter = ['camera_make', 'camera_model', 'taken_at', 'created_at']
    search_fields = ['image__title', 'camera_make', 'camera_model', 'location_name']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Image', {
            'fields': ('image',)
        }),
        ('Camera Information', {
            'fields': ('camera_make', 'camera_model', 'focal_length', 'aperture', 'iso', 'shutter_speed')
        }),
        ('Location', {
            'fields': ('gps_latitude', 'gps_longitude', 'location_name')
        }),
        ('Technical Data', {
            'fields': ('exif_data', 'color_palette'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('taken_at', 'created_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ImageSettings)
class ImageSettingsAdmin(admin.ModelAdmin):
    list_display = ['image', 'filter_applied', 'has_modifications', 'quality', 'watermark_enabled', 'updated_at']
    list_filter = ['filter_applied', 'watermark_enabled', 'updated_at']
    search_fields = ['image__title']
    readonly_fields = ['created_at', 'updated_at', 'has_modifications']
    
    fieldsets = (
        ('Image', {
            'fields': ('image',)
        }),
        ('Color Adjustments', {
            'fields': ('brightness', 'contrast', 'saturation', 'hue', 'sharpness', 'blur')
        }),
        ('Filters & Effects', {
            'fields': ('filter_applied', 'quality')
        }),
        ('Transformations', {
            'fields': ('crop_x', 'crop_y', 'crop_width', 'crop_height', 'rotation', 'flip_horizontal', 'flip_vertical')
        }),
        ('Watermark', {
            'fields': ('watermark_enabled', 'watermark_text', 'watermark_opacity')
        }),
        ('Timestamps', {
            'fields': ('has_modifications', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ImageLike)
class ImageLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'image', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'image__title']
    readonly_fields = ['created_at']


@admin.register(ImageComment)
class ImageCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'image', 'content_preview', 'parent', 'is_edited', 'created_at']
    list_filter = ['is_edited', 'created_at']
    search_fields = ['user__username', 'image__title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'


@admin.register(ImageShare)
class ImageShareAdmin(admin.ModelAdmin):
    list_display = ['user', 'image', 'share_type', 'recipient_email', 'view_count', 'expires_at', 'created_at']
    list_filter = ['share_type', 'created_at']
    search_fields = ['user__username', 'image__title', 'recipient_email']
    readonly_fields = ['share_token', 'view_count', 'created_at']


class ImageCollectionItemInline(admin.TabularInline):
    model = ImageCollectionItem
    extra = 0
    readonly_fields = ['added_at']


@admin.register(ImageCollection)
class ImageCollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'privacy', 'image_count_display', 'is_featured', 'created_at']
    list_filter = ['privacy', 'is_featured', 'created_at']
    search_fields = ['name', 'description', 'user__username']
    readonly_fields = ['id', 'image_count_display', 'created_at', 'updated_at']
    inlines = [ImageCollectionItemInline]
    
    def image_count_display(self, obj):
        return obj.image_count
    image_count_display.short_description = 'Images Count'


@admin.register(ImageCollectionItem)
class ImageCollectionItemAdmin(admin.ModelAdmin):
    list_display = ['collection', 'image', 'order', 'added_at']
    list_filter = ['added_at']
    search_fields = ['collection__name', 'image__title']
    readonly_fields = ['added_at']
