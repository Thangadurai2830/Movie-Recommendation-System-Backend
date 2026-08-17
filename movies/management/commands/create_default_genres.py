from django.core.management.base import BaseCommand
from movies.models import Genre


class Command(BaseCommand):
    help = 'Create default movie genres'
    
    def handle(self, *args, **options):
        genres = [
            'Action', 'Adventure', 'Animation', 'Comedy', 'Crime',
            'Documentary', 'Drama', 'Family', 'Fantasy', 'History',
            'Horror', 'Music', 'Mystery', 'Romance', 'Science Fiction',
            'Thriller', 'War', 'Western', 'Biography', 'Sport'
        ]
        
        created_count = 0
        for genre_name in genres:
            genre, created = Genre.objects.get_or_create(
                name=genre_name,
                defaults={'description': f'{genre_name} movies'}
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created genre: {genre_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Genre already exists: {genre_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_count} new genres. '
                f'Total genres: {Genre.objects.count()}'
            )
        )