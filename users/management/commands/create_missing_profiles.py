from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from users.models import UserProfile

User = get_user_model()

class Command(BaseCommand):
    help = 'Create missing UserProfile objects for existing users'

    def handle(self, *args, **options):
        users_without_profile = User.objects.filter(profile__isnull=True)
        count = users_without_profile.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('All users already have profiles.')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'Found {count} users without profiles. Creating...')
        )
        
        created_count = 0
        for user in users_without_profile:
            try:
                UserProfile.objects.create(user=user)
                created_count += 1
                self.stdout.write(f'Created profile for user: {user.username}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to create profile for {user.username}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} user profiles.')
        )