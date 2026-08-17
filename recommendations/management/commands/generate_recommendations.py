from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from movies.models import Movie, Rating
from users.models import User
from recommendations.models import Recommendation, UserPreference
from recommendations.ml_engine import RecommendationEngine
import logging
from datetime import datetime, timedelta
import time

logger = logging.getLogger('recommendations')

class Command(BaseCommand):
    help = 'Generate recommendations for users in batch mode'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user-ids',
            nargs='+',
            type=int,
            help='Specific user IDs to generate recommendations for'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of users to process in each batch (default: 100)'
        )
        parser.add_argument(
            '--recommendation-count',
            type=int,
            default=20,
            help='Number of recommendations per user (default: 20)'
        )
        parser.add_argument(
            '--algorithm',
            type=str,
            choices=['collaborative', 'content_based', 'hybrid', 'trending'],
            default='hybrid',
            help='Recommendation algorithm to use (default: hybrid)'
        )
        parser.add_argument(
            '--min-ratings',
            type=int,
            default=settings.ML_MIN_RATINGS_FOR_RECOMMENDATION,
            help='Minimum ratings required for personalized recommendations'
        )
        parser.add_argument(
            '--force-refresh',
            action='store_true',
            help='Force refresh existing recommendations'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually generating recommendations'
        )
        parser.add_argument(
            '--parallel',
            action='store_true',
            help='Use parallel processing for batch generation'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self.verbose = options['verbose']
        
        try:
            self.stdout.write(self.style.SUCCESS('Starting batch recommendation generation...'))
            
            # Get target users
            target_users = self._get_target_users(options)
            
            if not target_users:
                self.stdout.write(
                    self.style.WARNING('No users found for recommendation generation')
                )
                return
            
            if options['dry_run']:
                self._dry_run(target_users, options)
                return
            
            # Initialize recommendation engine
            engine = RecommendationEngine()
            
            # Process users in batches
            self._process_users_in_batches(engine, target_users, options)
            
            # Update cache and statistics
            self._update_statistics(target_users, options)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Batch recommendation generation completed for {len(target_users)} users!'
                )
            )
            
        except Exception as e:
            logger.error(f'Batch recommendation generation failed: {str(e)}')
            raise CommandError(f'Generation failed: {str(e)}')
    
    def _get_target_users(self, options):
        """Get list of users to generate recommendations for"""
        try:
            if options['user_ids']:
                # Specific user IDs provided
                users = User.objects.filter(
                    id__in=options['user_ids'],
                    is_active=True
                )
                
                if self.verbose:
                    self.stdout.write(f'Targeting {len(users)} specific users')
                
                return list(users)
            
            else:
                # All active users
                users = User.objects.filter(is_active=True)
                
                # Filter users who need recommendations
                if not options['force_refresh']:
                    # Exclude users with recent recommendations
                    recent_threshold = timezone.now() - timedelta(
                        hours=settings.ML_RECOMMENDATION_CACHE_TIMEOUT / 3600
                    )
                    
                    users_with_recent_recs = Recommendation.objects.filter(
                        created_at__gte=recent_threshold
                    ).values_list('user_id', flat=True).distinct()
                    
                    users = users.exclude(id__in=users_with_recent_recs)
                
                if self.verbose:
                    self.stdout.write(f'Targeting {users.count()} users for recommendations')
                
                return list(users)
                
        except Exception as e:
            logger.error(f'Failed to get target users: {str(e)}')
            raise
    
    def _dry_run(self, target_users, options):
        """Show what would be done without actually doing it"""
        self.stdout.write(self.style.WARNING('DRY RUN MODE - No recommendations will be generated'))
        
        batch_size = options['batch_size']
        num_batches = (len(target_users) + batch_size - 1) // batch_size
        
        self.stdout.write(f'Would process {len(target_users)} users in {num_batches} batches')
        self.stdout.write(f'Batch size: {batch_size}')
        self.stdout.write(f'Recommendations per user: {options["recommendation_count"]}')
        self.stdout.write(f'Algorithm: {options["algorithm"]}')
        self.stdout.write(f'Force refresh: {options["force_refresh"]}')
        
        # Show user distribution by rating count
        user_rating_counts = {}
        for user in target_users[:10]:  # Sample first 10 users
            rating_count = Rating.objects.filter(user=user).count()
            user_rating_counts[user.id] = rating_count
        
        self.stdout.write('\nSample user rating counts:')
        for user_id, count in user_rating_counts.items():
            self.stdout.write(f'  User {user_id}: {count} ratings')
    
    def _process_users_in_batches(self, engine, target_users, options):
        """Process users in batches"""
        batch_size = options['batch_size']
        total_users = len(target_users)
        num_batches = (total_users + batch_size - 1) // batch_size
        
        self.stdout.write(f'Processing {total_users} users in {num_batches} batches')
        
        success_count = 0
        error_count = 0
        
        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_users)
            batch_users = target_users[start_idx:end_idx]
            
            self.stdout.write(
                f'Processing batch {batch_num + 1}/{num_batches} '
                f'(users {start_idx + 1}-{end_idx})'
            )
            
            batch_start_time = time.time()
            
            # Process batch
            batch_success, batch_errors = self._process_batch(
                engine, batch_users, options
            )
            
            success_count += batch_success
            error_count += batch_errors
            
            batch_time = time.time() - batch_start_time
            
            if self.verbose:
                self.stdout.write(
                    f'  Batch completed in {batch_time:.2f}s '
                    f'(Success: {batch_success}, Errors: {batch_errors})'
                )
            
            # Small delay between batches to avoid overwhelming the system
            if batch_num < num_batches - 1:
                time.sleep(0.1)
        
        self.stdout.write(
            f'\nTotal: {success_count} successful, {error_count} errors'
        )
    
    def _process_batch(self, engine, batch_users, options):
        """Process a batch of users"""
        success_count = 0
        error_count = 0
        
        for user in batch_users:
            try:
                # Generate recommendations for user
                recommendations = self._generate_user_recommendations(
                    engine, user, options
                )
                
                if recommendations:
                    # Save recommendations
                    self._save_user_recommendations(user, recommendations, options)
                    success_count += 1
                    
                    if self.verbose:
                        self.stdout.write(
                            f'    Generated {len(recommendations)} recommendations for user {user.id}'
                        )
                else:
                    if self.verbose:
                        self.stdout.write(
                            f'    No recommendations generated for user {user.id}'
                        )
                
            except Exception as e:
                error_count += 1
                logger.error(
                    f'Failed to generate recommendations for user {user.id}: {str(e)}'
                )
                
                if self.verbose:
                    self.stdout.write(
                        self.style.ERROR(
                            f'    Error for user {user.id}: {str(e)}'
                        )
                    )
        
        return success_count, error_count
    
    def _generate_user_recommendations(self, engine, user, options):
        """Generate recommendations for a single user"""
        try:
            # Check if user has enough ratings for personalized recommendations
            user_rating_count = Rating.objects.filter(user=user).count()
            
            if user_rating_count < options['min_ratings']:
                # Use trending/popular recommendations for new users
                algorithm = 'trending'
            else:
                algorithm = options['algorithm']
            
            # Generate recommendations
            recommendations = engine.generate_recommendations(
                user_id=user.id,
                count=options['recommendation_count'],
                algorithm=algorithm
            )
            
            return recommendations
            
        except Exception as e:
            logger.error(
                f'Recommendation generation failed for user {user.id}: {str(e)}'
            )
            raise
    
    def _save_user_recommendations(self, user, recommendations, options):
        """Save recommendations for a user"""
        try:
            with transaction.atomic():
                # Clear existing recommendations if force refresh
                if options['force_refresh']:
                    Recommendation.objects.filter(user=user).delete()
                
                # Create new recommendations
                recommendation_objects = []
                for i, rec in enumerate(recommendations):
                    recommendation_objects.append(
                        Recommendation(
                            user=user,
                            movie_id=rec['movie_id'],
                            score=rec.get('score', 0.0),
                            algorithm=rec.get('algorithm', options['algorithm']),
                            rank=i + 1
                        )
                    )
                
                # Bulk create recommendations
                Recommendation.objects.bulk_create(
                    recommendation_objects,
                    ignore_conflicts=True
                )
                
                # Update cache
                cache_key = f'user_recommendations_{user.id}'
                cache.set(
                    cache_key,
                    recommendations,
                    timeout=settings.ML_RECOMMENDATION_CACHE_TIMEOUT
                )
                
        except Exception as e:
            logger.error(
                f'Failed to save recommendations for user {user.id}: {str(e)}'
            )
            raise
    
    def _update_statistics(self, target_users, options):
        """Update recommendation statistics"""
        try:
            # Update last generation timestamp
            cache.set(
                'last_batch_recommendation_generation',
                timezone.now(),
                timeout=None
            )
            
            # Update user statistics
            stats = {
                'total_users_processed': len(target_users),
                'algorithm_used': options['algorithm'],
                'recommendations_per_user': options['recommendation_count'],
                'generation_timestamp': timezone.now().isoformat()
            }
            
            cache.set(
                'batch_recommendation_stats',
                stats,
                timeout=86400  # 24 hours
            )
            
            if self.verbose:
                self.stdout.write('Updated recommendation statistics')
                
        except Exception as e:
            logger.warning(f'Failed to update statistics: {str(e)}')
    
    def _get_user_recommendation_status(self, user):
        """Get recommendation status for a user"""
        try:
            latest_rec = Recommendation.objects.filter(
                user=user
            ).order_by('-created_at').first()
            
            if latest_rec:
                age_hours = (
                    timezone.now() - latest_rec.created_at
                ).total_seconds() / 3600
                
                return {
                    'has_recommendations': True,
                    'last_generated': latest_rec.created_at,
                    'age_hours': age_hours,
                    'needs_refresh': age_hours > (
                        settings.ML_RECOMMENDATION_CACHE_TIMEOUT / 3600
                    )
                }
            else:
                return {
                    'has_recommendations': False,
                    'needs_refresh': True
                }
                
        except Exception as e:
            logger.error(f'Failed to get recommendation status for user {user.id}: {str(e)}')
            return {'has_recommendations': False, 'needs_refresh': True}