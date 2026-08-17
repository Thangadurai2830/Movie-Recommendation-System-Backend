from rest_framework import generics, status, permissions, filters
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg, F, Case, When, IntegerField
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.http import HttpResponse, Http404
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import os
import logging
import json
from datetime import datetime, timedelta
from uuid import uuid4

from .models import (
    ImageProfile, ImageUpload, ImageMetadata, ImageSettings,
    ImageLike, ImageComment, ImageShare, ImageCollection, ImageCollectionItem
)
from .serializers import (
    ImageProfileSerializer, ImageUploadSerializer, ImageUploadListSerializer,
    ImageMetadataSerializer, ImageSettingsSerializer, ImageLikeSerializer,
    ImageCommentSerializer, ImageShareSerializer, ImageCollectionSerializer,
    ImageCollectionListSerializer, ImageCollectionItemSerializer,
    BulkImageActionSerializer
)
from notifications.utils import NotificationManager

User = get_user_model()
logger = logging.getLogger(__name__)


class ImagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ImageProfileView(generics.RetrieveUpdateAPIView):
    """Get or update user's image profile settings"""
    serializer_class = ImageProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        profile, created = ImageProfile.objects.get_or_create(user=self.request.user)
        return profile


class ImageUploadView(generics.CreateAPIView):
    """Upload a new image"""
    serializer_class = ImageUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [UserRateThrottle]
    
    def perform_create(self, serializer):
        image_instance = serializer.save(user=self.request.user)
        
        # Process image metadata
        if image_instance.image:
            try:
                with Image.open(image_instance.image.path) as img:
                    # Update image dimensions and format
                    image_instance.width = img.width
                    image_instance.height = img.height
                    image_instance.format = img.format
                    image_instance.file_size = os.path.getsize(image_instance.image.path)
                    
                    # Extract EXIF data
                    exif_data = {}
                    if hasattr(img, '_getexif') and img._getexif():
                        exif_data = dict(img._getexif())
                    
                    # Create metadata record
                    ImageMetadata.objects.create(
                        image=image_instance,
                        exif_data=exif_data
                    )
                    
                    # Create default settings
                    ImageSettings.objects.create(image=image_instance)
                    
                    image_instance.save()
                    
            except Exception as e:
                logger.error(f"Error processing image metadata: {e}")
        
        # Send notification
        NotificationManager.create_notification(
            user=self.request.user,
            notification_type='image_uploaded',
            title='Image Uploaded Successfully',
            message=f'Your image "{image_instance.title or "Untitled"}" has been uploaded.',
            data={'image_id': str(image_instance.id)}
        )


class ImageListView(generics.ListAPIView):
    """List images with filtering and search"""
    serializer_class = ImageUploadListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = ImagePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['privacy', 'status', 'is_featured', 'user']
    search_fields = ['title', 'description', 'tags']
    ordering_fields = ['created_at', 'views_count', 'likes_count', 'title']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = ImageUpload.objects.select_related('user').prefetch_related('likes')
        
        # Filter by privacy settings
        if self.request.user.is_authenticated:
            queryset = queryset.filter(
                Q(privacy='public') |
                Q(user=self.request.user) |
                Q(privacy='friends', user__in=self.request.user.friends.all())
            )
        else:
            queryset = queryset.filter(privacy='public')
        
        # Filter by status
        queryset = queryset.filter(status='published')
        
        return queryset


class ImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a specific image"""
    serializer_class = ImageUploadSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'id'
    
    def get_queryset(self):
        return ImageUpload.objects.select_related(
            'user', 'metadata', 'settings'
        ).prefetch_related('likes', 'comments')
    
    def get_object(self):
        obj = super().get_object()
        
        # Check privacy permissions
        if obj.privacy == 'private' and obj.user != self.request.user:
            raise Http404("Image not found")
        elif obj.privacy == 'friends' and not self.request.user.is_authenticated:
            raise Http404("Image not found")
        elif obj.privacy == 'friends' and obj.user != self.request.user:
            # Check if users are friends (implement friend system if needed)
            pass
        
        # Increment view count
        if self.request.method == 'GET' and obj.user != self.request.user:
            obj.views_count = F('views_count') + 1
            obj.save(update_fields=['views_count'])
            obj.refresh_from_db()
        
        return obj
    
    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            raise permissions.PermissionDenied("You can only edit your own images.")
        serializer.save()
    
    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise permissions.PermissionDenied("You can only delete your own images.")
        instance.delete()


class ImageSettingsView(generics.RetrieveUpdateAPIView):
    """Get or update image appearance settings"""
    serializer_class = ImageSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        image_id = self.kwargs['image_id']
        image = get_object_or_404(ImageUpload, id=image_id, user=self.request.user)
        settings, created = ImageSettings.objects.get_or_create(image=image)
        return settings


class ProcessImageView(APIView):
    """Apply image processing based on settings"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, image_id):
        try:
            image = get_object_or_404(ImageUpload, id=image_id, user=request.user)
            settings = get_object_or_404(ImageSettings, image=image)
            
            # Open the original image
            with Image.open(image.image.path) as img:
                processed_img = img.copy()
                
                # Apply brightness
                if settings.brightness != 0:
                    enhancer = ImageEnhance.Brightness(processed_img)
                    factor = 1 + (settings.brightness / 100)
                    processed_img = enhancer.enhance(factor)
                
                # Apply contrast
                if settings.contrast != 0:
                    enhancer = ImageEnhance.Contrast(processed_img)
                    factor = 1 + (settings.contrast / 100)
                    processed_img = enhancer.enhance(factor)
                
                # Apply saturation
                if settings.saturation != 0:
                    enhancer = ImageEnhance.Color(processed_img)
                    factor = 1 + (settings.saturation / 100)
                    processed_img = enhancer.enhance(factor)
                
                # Apply sharpness
                if settings.sharpness != 0:
                    enhancer = ImageEnhance.Sharpness(processed_img)
                    factor = 1 + (settings.sharpness / 100)
                    processed_img = enhancer.enhance(factor)
                
                # Apply blur
                if settings.blur > 0:
                    processed_img = processed_img.filter(
                        ImageFilter.GaussianBlur(radius=settings.blur / 10)
                    )
                
                # Apply rotation
                if settings.rotation != 0:
                    processed_img = processed_img.rotate(settings.rotation, expand=True)
                
                # Apply flips
                if settings.flip_horizontal:
                    processed_img = processed_img.transpose(Image.FLIP_LEFT_RIGHT)
                if settings.flip_vertical:
                    processed_img = processed_img.transpose(Image.FLIP_TOP_BOTTOM)
                
                # Apply crop
                if all([settings.crop_width, settings.crop_height]):
                    box = (
                        settings.crop_x,
                        settings.crop_y,
                        settings.crop_x + settings.crop_width,
                        settings.crop_y + settings.crop_height
                    )
                    processed_img = processed_img.crop(box)
                
                # Apply filters
                if settings.filter_applied != 'none':
                    processed_img = self.apply_filter(processed_img, settings.filter_applied)
                
                # Save processed image
                processed_path = self.save_processed_image(processed_img, image, settings)
                
                return Response({
                    'success': True,
                    'processed_image_url': processed_path,
                    'message': 'Image processed successfully'
                })
                
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def apply_filter(self, img, filter_name):
        """Apply predefined filters"""
        if filter_name == 'black_white':
            return img.convert('L').convert('RGB')
        elif filter_name == 'sepia':
            return ImageOps.colorize(img.convert('L'), '#704214', '#C0A882')
        elif filter_name == 'vintage':
            # Apply vintage effect
            enhancer = ImageEnhance.Color(img)
            img = enhancer.enhance(0.8)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)
            return img
        elif filter_name == 'vibrant':
            enhancer = ImageEnhance.Color(img)
            return enhancer.enhance(1.5)
        elif filter_name == 'cool':
            # Apply cool tone
            return img
        elif filter_name == 'warm':
            # Apply warm tone
            return img
        elif filter_name == 'dramatic':
            enhancer = ImageEnhance.Contrast(img)
            return enhancer.enhance(1.8)
        return img
    
    def save_processed_image(self, img, original_image, settings):
        """Save the processed image"""
        # Generate unique filename
        filename = f"processed_{uuid4().hex}.jpg"
        processed_dir = os.path.join(os.path.dirname(original_image.image.path), 'processed')
        os.makedirs(processed_dir, exist_ok=True)
        processed_path = os.path.join(processed_dir, filename)
        
        # Save with quality setting
        img.save(processed_path, 'JPEG', quality=settings.quality, optimize=True)
        
        # Return relative URL
        return processed_path.replace(os.path.dirname(original_image.image.path), '').lstrip('/')


class ImageLikeView(APIView):
    """Like or unlike an image"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, image_id):
        image = get_object_or_404(ImageUpload, id=image_id)
        like, created = ImageLike.objects.get_or_create(
            user=request.user,
            image=image
        )
        
        if not created:
            like.delete()
            liked = False
            message = 'Image unliked'
        else:
            liked = True
            message = 'Image liked'
            
            # Send notification to image owner
            if image.user != request.user:
                NotificationManager.create_notification(
                    user=image.user,
                    notification_type='image_liked',
                    title='Someone liked your image',
                    message=f'{request.user.username} liked your image "{image.title or "Untitled"}"',
                    data={'image_id': str(image.id), 'liker_id': request.user.id}
                )
        
        return Response({
            'liked': liked,
            'likes_count': image.likes.count(),
            'message': message
        })


class ImageCommentListCreateView(generics.ListCreateAPIView):
    """List and create comments for an image"""
    serializer_class = ImageCommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = ImagePagination
    
    def get_queryset(self):
        image_id = self.kwargs['image_id']
        return ImageComment.objects.filter(
            image_id=image_id,
            parent=None
        ).select_related('user').prefetch_related('replies')
    
    def perform_create(self, serializer):
        image_id = self.kwargs['image_id']
        image = get_object_or_404(ImageUpload, id=image_id)
        comment = serializer.save(user=self.request.user, image=image)
        
        # Send notification to image owner
        if image.user != self.request.user:
            NotificationManager.create_notification(
                user=image.user,
                notification_type='image_commented',
                title='New comment on your image',
                message=f'{self.request.user.username} commented on your image "{image.title or "Untitled"}"',
                data={'image_id': str(image.id), 'comment_id': comment.id}
            )


class ImageShareView(generics.CreateAPIView):
    """Share an image"""
    serializer_class = ImageShareSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        image_id = self.kwargs['image_id']
        image = get_object_or_404(ImageUpload, id=image_id)
        
        # Check if user can share this image
        if image.privacy == 'private' and image.user != self.request.user:
            raise permissions.PermissionDenied("Cannot share private images.")
        
        serializer.save(user=self.request.user, image=image)


class ImageCollectionListCreateView(generics.ListCreateAPIView):
    """List and create image collections"""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ImagePagination
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ImageCollectionListSerializer
        return ImageCollectionSerializer
    
    def get_queryset(self):
        return ImageCollection.objects.filter(
            user=self.request.user
        ).select_related('user', 'cover_image')


class ImageCollectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an image collection"""
    serializer_class = ImageCollectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return ImageCollection.objects.filter(
            user=self.request.user
        ).prefetch_related('items__image')


class AddImageToCollectionView(APIView):
    """Add images to a collection"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, collection_id):
        collection = get_object_or_404(
            ImageCollection,
            id=collection_id,
            user=request.user
        )
        
        image_ids = request.data.get('image_ids', [])
        if not image_ids:
            return Response(
                {'error': 'No image IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        images = ImageUpload.objects.filter(
            id__in=image_ids,
            user=request.user
        )
        
        added_count = 0
        for image in images:
            item, created = ImageCollectionItem.objects.get_or_create(
                collection=collection,
                image=image,
                defaults={'order': collection.items.count()}
            )
            if created:
                added_count += 1
        
        return Response({
            'success': True,
            'added_count': added_count,
            'total_images': collection.items.count()
        })


class BulkImageActionView(APIView):
    """Perform bulk actions on images"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = BulkImageActionSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image_ids = serializer.validated_data['image_ids']
        action = serializer.validated_data['action']
        
        images = ImageUpload.objects.filter(
            id__in=image_ids,
            user=request.user
        )
        
        updated_count = 0
        
        if action == 'delete':
            updated_count = images.count()
            images.delete()
        elif action.startswith('privacy_'):
            privacy_level = action.split('_')[1]
            updated_count = images.update(privacy=privacy_level)
        elif action == 'feature':
            updated_count = images.update(is_featured=True)
        elif action == 'unfeature':
            updated_count = images.update(is_featured=False)
        
        return Response({
            'success': True,
            'action': action,
            'updated_count': updated_count
        })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_image_stats(request):
    """Get user's image statistics"""
    user = request.user
    
    stats = {
        'total_images': ImageUpload.objects.filter(user=user).count(),
        'total_likes': ImageLike.objects.filter(image__user=user).count(),
        'total_comments': ImageComment.objects.filter(image__user=user).count(),
        'total_views': ImageUpload.objects.filter(user=user).aggregate(
            total=models.Sum('views_count')
        )['total'] or 0,
        'collections_count': ImageCollection.objects.filter(user=user).count(),
        'featured_images': ImageUpload.objects.filter(user=user, is_featured=True).count(),
    }
    
    return Response(stats)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def shared_image_view(request, share_token):
    """View a shared image"""
    try:
        share = get_object_or_404(ImageShare, share_token=share_token)
        
        # Check if share has expired
        if share.expires_at and share.expires_at < timezone.now():
            raise Http404("Share link has expired")
        
        # Increment view count
        share.view_count = F('view_count') + 1
        share.save(update_fields=['view_count'])
        
        # Return image data
        serializer = ImageUploadSerializer(share.image, context={'request': request})
        return Response({
            'image': serializer.data,
            'share_info': {
                'shared_by': share.user.username,
                'shared_at': share.created_at,
                'view_count': share.view_count
            }
        })
        
    except ImageShare.DoesNotExist:
        raise Http404("Invalid share link")
