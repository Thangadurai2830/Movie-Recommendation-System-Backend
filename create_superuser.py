#!/usr/bin/env python
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_recommendation.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def create_superuser(email, password, first_name="Admin", last_name="User"):
    """Create a superuser with given credentials"""
    try:
        if User.objects.filter(email=email).exists():
            print(f"User with email {email} already exists!")
            return False
            
        user = User.objects.create_superuser(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        print(f"Superuser created successfully!")
        print(f"ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Name: {user.first_name} {user.last_name}")
        return True
    except Exception as e:
        print(f"Error creating superuser: {e}")
        return False

def delete_superuser(email):
    """Delete a superuser by email"""
    try:
        user = User.objects.get(email=email, is_superuser=True)
        user.delete()
        print(f"Superuser {email} deleted successfully!")
        return True
    except User.DoesNotExist:
        print(f"Superuser with email {email} not found!")
        return False
    except Exception as e:
        print(f"Error deleting superuser: {e}")
        return False

def list_superusers():
    """List all superusers"""
    superusers = User.objects.filter(is_superuser=True)
    print(f"Total superusers: {superusers.count()}")
    print("=" * 40)
    
    for user in superusers:
        print(f"ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Name: {user.first_name} {user.last_name}")
        print(f"Active: {user.is_active}")
        print(f"Date Joined: {user.date_joined}")
        print("-" * 30)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python create_superuser.py list")
        print("  python create_superuser.py create <email> <password> [first_name] [last_name]")
        print("  python create_superuser.py delete <email>")
        print("\nExamples:")
        print("  python create_superuser.py list")
        print("  python create_superuser.py create admin@movie.com mypassword123 John Doe")
        print("  python create_superuser.py delete admin@example.com")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_superusers()
    
    elif command == "create":
        if len(sys.argv) < 4:
            print("Error: Email and password are required for create command")
            print("Usage: python create_superuser.py create <email> <password> [first_name] [last_name]")
            return
        
        email = sys.argv[2]
        password = sys.argv[3]
        first_name = sys.argv[4] if len(sys.argv) > 4 else "Admin"
        last_name = sys.argv[5] if len(sys.argv) > 5 else "User"
        
        create_superuser(email, password, first_name, last_name)
    
    elif command == "delete":
        if len(sys.argv) < 3:
            print("Error: Email is required for delete command")
            print("Usage: python create_superuser.py delete <email>")
            return
        
        email = sys.argv[2]
        delete_superuser(email)
    
    else:
        print(f"Unknown command: {command}")
        print("Available commands: list, create, delete")

if __name__ == '__main__':
    main()