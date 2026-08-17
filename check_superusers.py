#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_recommendation.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("Current superusers in the database:")
print("=" * 40)

superusers = User.objects.filter(is_superuser=True)

if superusers.exists():
    for user in superusers:
        print(f"ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"First Name: {user.first_name}")
        print(f"Last Name: {user.last_name}")
        print(f"Is Active: {user.is_active}")
        print(f"Date Joined: {user.date_joined}")
        print("-" * 30)
else:
    print("No superusers found in the database.")

print(f"\nTotal users in database: {User.objects.count()}")
print(f"Total superusers: {superusers.count()}")