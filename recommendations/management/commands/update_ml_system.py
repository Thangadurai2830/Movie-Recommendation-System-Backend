from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from movies.models import Movie, Rating, Genre
from users.models import User
from recommendations.models import Recommendation, UserPreference, UserMovieInteraction
import logging
from datetime import datetime, timedelta
import os
import json

logger = logging.getLogger('recommendations')

class Command(BaseCommand):
    help = 'Update and maintain the ML recommendation system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            choices=[
                'full_update', 'retrain_models', 'refresh_recommendations',
                'cleanup_old_data', 'update_statistics', 'health_check'
            ],
            default='full_update',
            help='Specific maintenance task to perform (default: full_update)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if recent update exists'
        )
        parser.add_argument(
            '--cleanup-days',
            type=int,
            default=30,
            help='Days of old data to keep during cleanup (default: 30)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for processing operations (default: 1000)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it'
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
            task = options['task']
            
            self.stdout.write(
                self.style.SUCCESS(f'Starting ML system maintenance: {task}')
            )
            
            if options['dry_run']:
                self._dry_run(task, options)
                return
            
            # Execute the specified task
            if task == 'full_update':
                self._full_update(options)
            elif task == 'retrain_models':
                self._retrain_models(options)
            elif task == 'refresh_recommendations':
                self._refresh_recommendations(options)
            elif task == 'cleanup_old_data':
                self._cleanup_old_data(options)
            elif task == 'update_statistics':
                self._update_statistics(options)
            elif task == 'health_check':
                self._health_check(options)
            
            self.stdout.write(
                self.style.SUCCESS(f'ML system maintenance completed: {task}')
            )
            
        except Exception as e:
            logger.error(f'ML system maintenance failed: {str(e)}')
            raise CommandError(f'Maintenance failed: {str(e)}')
    
    def _dry_run(self, task, options):
        """Show what would be done without actually doing it"""
        self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        if task == 'full_update':
            self.stdout.write('Would perform:')
            self.stdout.write('  1. Health check')
            self.stdout.write('  2. Data preprocessing')
            self.stdout.write('  3. Model retraining')
            self.stdout.write('  4. Recommendation refresh')
            self.stdout.write('  5. Statistics update')
            self.stdout.write('  6. Old data cleanup')
        
        elif task == 'cleanup_old_data':
            cutoff_date = timezone.now() - timedelta(days=options['cleanup_days'])
            
            old_recommendations = Recommendation.objects.filter(
                created_at__lt=cutoff_date
            ).count()
            old_interactions = UserMovieInteraction.objects.filter(
                created_at__lt=cutoff_date
            ).count()
            
            self.stdout.write(f'Would delete:')
            self.stdout.write(f'  {old_recommendations} old recommendations')
            self.stdout.write(f'  {old_interactions} old interactions')
        
        elif task == 'refresh_recommendations':
            active_users = User.objects.filter(is_active=True).count()
            self.stdout.write(f'Would refresh recommendations for {active_users} users')
        
        self.stdout.write(f'\nTask: {task}')
        self.stdout.write(f'Force: {options["force"]}')
        self.stdout.write(f'Batch size: {options["batch_size"]}')
    
    def _full_update(self, options):
        """Perform a full system update"""
        self.stdout.write('Performing full ML system update...')
        
        # 1. Health check
        self.stdout.write('Step 1/6: Health check')
        health_status = self._health_check(options, silent=True)
        
        if not health_status['healthy'] and not options['force']:
            raise CommandError(
                f'System health check failed: {health_status["issues"]}. '
                'Use --force to proceed anyway.'
            )
        
        # 2. Data preprocessing
        self.stdout.write('Step 2/6: Data preprocessing')
        try:
            call_command(
                'preprocess_data',
                feature_types=['all'],
                normalize=True,
                save_encoders=True,
                verbosity=0 if not self.verbose else 2
            )
        except Exception as e:
            logger.warning(f'Data preprocessing failed: {str(e)}')
        
        # 3. Model retraining
        self.stdout.write('Step 3/6: Model retraining')
        self._retrain_models(options)
        
        # 4. Recommendation refresh
        self.stdout.write('Step 4/6: Recommendation refresh')
        self._refresh_recommendations(options)
        
        # 5. Statistics update
        self.stdout.write('Step 5/6: Statistics update')
        self._update_statistics(options)
        
        # 6. Cleanup old data
        self.stdout.write('Step 6/6: Cleanup old data')
        self._cleanup_old_data(options)
        
        # Update last full update timestamp
        cache.set('last_full_ml_update', timezone.now(), timeout=None)
    
    def _retrain_models(self, options):
        """Retrain ML models"""
        self.stdout.write('Retraining ML models...')
        
        try:
            # Check if retraining is needed
            if not options['force'] and not self._needs_retraining():
                self.stdout.write(
                    self.style.WARNING('Models are up to date. Use --force to retrain.')
                )
                return
            
            # Call the training command
            call_command(
                'train_ml_models',
                algorithm='all',
                save_model=True,
                evaluate=True,
                force=options['force'],
                verbosity=0 if not self.verbose else 2
            )
            
            if self.verbose:
                self.stdout.write('Model retraining completed')
                
        except Exception as e:
            logger.error(f'Model retraining failed: {str(e)}')
            raise
    
    def _refresh_recommendations(self, options):
        """Refresh user recommendations"""
        self.stdout.write('Refreshing user recommendations...')
        
        try:
            # Call the recommendation generation command
            call_command(
                'generate_recommendations',
                batch_size=options['batch_size'],
                algorithm='hybrid',
                force_refresh=options['force'],
                verbosity=0 if not self.verbose else 2
            )
            
            if self.verbose:
                self.stdout.write('Recommendation refresh completed')
                
        except Exception as e:
            logger.error(f'Recommendation refresh failed: {str(e)}')
            raise
    
    def _cleanup_old_data(self, options):
        """Clean up old data"""
        self.stdout.write('Cleaning up old data...')
        
        try:
            cutoff_date = timezone.now() - timedelta(days=options['cleanup_days'])
            
            # Clean up old recommendations
            old_recommendations = Recommendation.objects.filter(
                created_at__lt=cutoff_date
            )
            rec_count = old_recommendations.count()
            
            if rec_count > 0:
                old_recommendations.delete()
                self.stdout.write(f'Deleted {rec_count} old recommendations')
            
            # Clean up old interactions (keep more recent ones)
            interaction_cutoff = timezone.now() - timedelta(days=options['cleanup_days'] * 2)
            old_interactions = UserMovieInteraction.objects.filter(
                created_at__lt=interaction_cutoff
            )
            interaction_count = old_interactions.count()
            
            if interaction_count > 0:
                old_interactions.delete()
                self.stdout.write(f'Deleted {interaction_count} old interactions')
            
            # Clean up cache
            self._cleanup_cache()
            
            if self.verbose:
                self.stdout.write('Data cleanup completed')
                
        except Exception as e:
            logger.error(f'Data cleanup failed: {str(e)}')
            raise
    
    def _update_statistics(self, options):
        """Update system statistics"""
        self.stdout.write('Updating system statistics...')
        
        try:
            # Collect system statistics
            stats = {
                'timestamp': timezone.now().isoformat(),
                'users': {
                    'total': User.objects.count(),
                    'active': User.objects.filter(is_active=True).count(),
                    'with_preferences': UserPreference.objects.count(),
                    'with_ratings': User.objects.filter(
                        rating__isnull=False
                    ).distinct().count()
                },
                'movies': {
                    'total': Movie.objects.count(),
                    'with_ratings': Movie.objects.filter(
                        rating__isnull=False
                    ).distinct().count(),
                    'genres': Genre.objects.count()
                },
                'ratings': {
                    'total': Rating.objects.count(),
                    'avg_rating': self._get_average_rating(),
                    'recent_24h': Rating.objects.filter(
                        created_at__gte=timezone.now() - timedelta(hours=24)
                    ).count()
                },
                'recommendations': {
                    'total': Recommendation.objects.count(),
                    'recent_24h': Recommendation.objects.filter(
                        created_at__gte=timezone.now() - timedelta(hours=24)
                    ).count(),
                    'users_with_recs': Recommendation.objects.values(
                        'user'
                    ).distinct().count()
                },
                'interactions': {
                    'total': UserMovieInteraction.objects.count(),
                    'recent_24h': UserMovieInteraction.objects.filter(
                        created_at__gte=timezone.now() - timedelta(hours=24)
                    ).count()
                }
            }
            
            # Save statistics to cache
            cache.set('ml_system_statistics', stats, timeout=86400)  # 24 hours
            
            # Save to file for historical tracking
            self._save_statistics_to_file(stats)
            
            if self.verbose:
                self.stdout.write('System statistics updated')
                self._display_statistics(stats)
                
        except Exception as e:
            logger.error(f'Statistics update failed: {str(e)}')
            raise
    
    def _health_check(self, options, silent=False):
        """Perform system health check"""
        if not silent:
            self.stdout.write('Performing system health check...')
        
        issues = []
        warnings = []
        
        try:
            # Check data availability
            user_count = User.objects.filter(is_active=True).count()
            movie_count = Movie.objects.count()
            rating_count = Rating.objects.count()
            
            if user_count < 10:
                issues.append(f'Too few active users: {user_count}')
            elif user_count < 100:
                warnings.append(f'Low user count: {user_count}')
            
            if movie_count < 100:
                issues.append(f'Too few movies: {movie_count}')
            elif movie_count < 1000:
                warnings.append(f'Low movie count: {movie_count}')
            
            if rating_count < settings.ML_MIN_RATINGS_FOR_RECOMMENDATION:
                issues.append(
                    f'Insufficient ratings: {rating_count} '
                    f'(need {settings.ML_MIN_RATINGS_FOR_RECOMMENDATION})'
                )
            
            # Check model freshness
            last_training = cache.get('ml_last_training')
            if last_training:
                hours_since = (timezone.now() - last_training).total_seconds() / 3600
                if hours_since > settings.ML_MODEL_UPDATE_INTERVAL * 2:
                    warnings.append(
                        f'Models are stale: {hours_since:.1f} hours since last training'
                    )
            else:
                issues.append('No training timestamp found')
            
            # Check cache health
            try:
                cache.set('health_check_test', 'ok', timeout=60)
                if cache.get('health_check_test') != 'ok':
                    warnings.append('Cache not working properly')
                cache.delete('health_check_test')
            except Exception:
                warnings.append('Cache system issues detected')
            
            # Check database connectivity
            try:
                list(User.objects.all()[:1])
            except Exception as e:
                issues.append(f'Database connectivity issue: {str(e)}')
            
            # Determine overall health
            healthy = len(issues) == 0
            
            health_status = {
                'healthy': healthy,
                'issues': issues,
                'warnings': warnings,
                'stats': {
                    'users': user_count,
                    'movies': movie_count,
                    'ratings': rating_count
                }
            }
            
            if not silent:
                self._display_health_status(health_status)
            
            return health_status
            
        except Exception as e:
            logger.error(f'Health check failed: {str(e)}')
            return {
                'healthy': False,
                'issues': [f'Health check error: {str(e)}'],
                'warnings': [],
                'stats': {}
            }
    
    def _needs_retraining(self):
        """Check if models need retraining"""
        last_training = cache.get('ml_last_training')
        if not last_training:
            return True
        
        hours_since = (timezone.now() - last_training).total_seconds() / 3600
        return hours_since >= settings.ML_MODEL_UPDATE_INTERVAL
    
    def _get_average_rating(self):
        """Get average rating across all ratings"""
        from django.db.models import Avg
        result = Rating.objects.aggregate(avg_rating=Avg('rating'))
        return round(result['avg_rating'] or 0, 2)
    
    def _cleanup_cache(self):
        """Clean up stale cache entries"""
        try:
            # Clear old recommendation caches
            # Note: This is a simplified approach. In production, you might want
            # to use cache versioning or more sophisticated cache management
            cache.clear()
            
            if self.verbose:
                self.stdout.write('Cache cleaned up')
                
        except Exception as e:
            logger.warning(f'Cache cleanup failed: {str(e)}')
    
    def _save_statistics_to_file(self, stats):
        """Save statistics to file for historical tracking"""
        try:
            stats_dir = settings.BASE_DIR / 'ml_statistics'
            stats_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'ml_stats_{timestamp}.json'
            filepath = stats_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(stats, f, indent=2, default=str)
            
            if self.verbose:
                self.stdout.write(f'Statistics saved to {filepath}')
                
        except Exception as e:
            logger.warning(f'Failed to save statistics to file: {str(e)}')
    
    def _display_health_status(self, health_status):
        """Display health check results"""
        if health_status['healthy']:
            self.stdout.write(self.style.SUCCESS('✓ System is healthy'))
        else:
            self.stdout.write(self.style.ERROR('✗ System has issues'))
        
        if health_status['issues']:
            self.stdout.write(self.style.ERROR('Issues:'))
            for issue in health_status['issues']:
                self.stdout.write(f'  - {issue}')
        
        if health_status['warnings']:
            self.stdout.write(self.style.WARNING('Warnings:'))
            for warning in health_status['warnings']:
                self.stdout.write(f'  - {warning}')
        
        stats = health_status['stats']
        if stats:
            self.stdout.write('System Stats:')
            self.stdout.write(f'  Users: {stats.get("users", 0)}')
            self.stdout.write(f'  Movies: {stats.get("movies", 0)}')
            self.stdout.write(f'  Ratings: {stats.get("ratings", 0)}')
    
    def _display_statistics(self, stats):
        """Display system statistics"""
        self.stdout.write('\nSystem Statistics:')
        
        users = stats['users']
        self.stdout.write(f'Users: {users["total"]} total, {users["active"]} active')
        
        movies = stats['movies']
        self.stdout.write(f'Movies: {movies["total"]} total, {movies["with_ratings"]} with ratings')
        
        ratings = stats['ratings']
        self.stdout.write(
            f'Ratings: {ratings["total"]} total, '
            f'avg: {ratings["avg_rating"]}, '
            f'{ratings["recent_24h"]} in last 24h'
        )
        
        recommendations = stats['recommendations']
        self.stdout.write(
            f'Recommendations: {recommendations["total"]} total, '
            f'{recommendations["recent_24h"]} in last 24h'
        )