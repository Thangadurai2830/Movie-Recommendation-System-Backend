from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'images'

urlpatterns = [
    # Image Profile
    path('profile/', views.ImageProfileView.as_view(), name='image-profile'),
    
    # Image Upload and Management
    path('upload/', views.ImageUploadView.as_view(), name='image-upload'),
    path('list/', views.ImageListView.as_view(), name='image-list'),
    path('<uuid:id>/', views.ImageDetailView.as_view(), name='image-detail'),
    
    # Image Settings and Processing
    path('<uuid:image_id>/settings/', views.ImageSettingsView.as_view(), name='image-settings'),
    path('<uuid:image_id>/process/', views.ProcessImageView.as_view(), name='image-process'),
    
    # Image Interactions
    path('<uuid:image_id>/like/', views.ImageLikeView.as_view(), name='image-like'),
    path('<uuid:image_id>/comments/', views.ImageCommentListCreateView.as_view(), name='image-comments'),
    path('<uuid:image_id>/share/', views.ImageShareView.as_view(), name='image-share'),
    
    # Image Collections
    path('collections/', views.ImageCollectionListCreateView.as_view(), name='collection-list'),
    path('collections/<uuid:id>/', views.ImageCollectionDetailView.as_view(), name='collection-detail'),
    path('collections/<uuid:collection_id>/add-images/', views.AddImageToCollectionView.as_view(), name='collection-add-images'),
    
    # Bulk Operations
    path('bulk-action/', views.BulkImageActionView.as_view(), name='bulk-action'),
    
    # Statistics and Analytics
    path('stats/', views.user_image_stats, name='user-stats'),
    
    # Shared Images
    path('shared/<str:share_token>/', views.shared_image_view, name='shared-image'),
]