#!/usr/bin/env python
"""
Script to set password for a user
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_recommendation.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def set_user_password(email, password):
    """Set password for a user"""
    try:
        user = User.objects.get(email=email)
        user.set_password(password)
        user.save()
        print(f"Password set successfully for user: {email}")
        return True
    except User.DoesNotExist:
        print(f"User with email {email} does not exist")
        return False
    except Exception as e:
        print(f"Error setting password: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python set_password.py <email> <password>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    set_user_password(email, password)