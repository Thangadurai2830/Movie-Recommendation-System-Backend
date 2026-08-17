from django.core.management.base import BaseCommand
import asyncio
import logging
from movies.realtime_service import realtime_service

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start the real-time movie streaming service'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=300,
            help='Update interval in seconds (default: 300)'
        )
    
    def handle(self, *args, **options):
        interval = options['interval']
        realtime_service.update_interval = interval
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting real-time movie streaming service with {interval}s interval...'
            )
        )
        
        try:
            asyncio.run(realtime_service.start_streaming())
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('Stopping real-time streaming service...')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error in streaming service: {str(e)}')
            )
            logger.error(f'Real-time streaming service error: {str(e)}')