from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import IntegrityError
import getpass

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser for admin access'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the superuser',
            default='admin'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email for the superuser',
            default='admin@movierecommendation.com'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the superuser (will prompt if not provided)'
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Create superuser without prompting for input'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        noinput = options['noinput']

        # Check if superuser already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Superuser "{username}" already exists!')
            )
            return

        # Get password if not provided
        if not password and not noinput:
            password = getpass.getpass('Password: ')
            password_confirm = getpass.getpass('Password (again): ')
            
            if password != password_confirm:
                self.stdout.write(
                    self.style.ERROR('Passwords do not match!')
                )
                return
        elif not password and noinput:
            password = 'admin123'  # Default password for non-interactive mode

        try:
            # Create superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name='Admin',
                last_name='User'
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Superuser "{username}" created successfully!\n'
                    f'Email: {email}\n'
                    f'You can now access the admin panel at: http://localhost:8000/admin/'
                )
            )
            
            if noinput:
                self.stdout.write(
                    self.style.WARNING(
                        f'Default password used: {password}\n'
                        'Please change this password after first login!'
                    )
                )
                
        except IntegrityError as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {e}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Unexpected error: {e}')
            )