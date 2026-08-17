#!/usr/bin/env python
import os
import django
import getpass

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_recommendation.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def delete_all_superusers():
    """Delete all existing superusers"""
    superusers = User.objects.filter(is_superuser=True)
    count = superusers.count()
    
    if count > 0:
        print(f"Found {count} superuser(s). Deleting...")
        for user in superusers:
            print(f"Deleting superuser: {user.email} (ID: {user.id})")
            user.delete()
        print("All superusers deleted successfully!")
    else:
        print("No superusers found to delete.")

def create_new_superuser():
    """Create a new superuser with custom credentials"""
    print("\nCreating new superuser...")
    print("Please provide the following information:")
    
    email = input("Email address: ").strip()
    while not email or '@' not in email:
        print("Please enter a valid email address.")
        email = input("Email address: ").strip()
    
    first_name = input("First name: ").strip()
    last_name = input("Last name: ").strip()
    
    password = getpass.getpass("Password: ")
    while len(password) < 8:
        print("Password must be at least 8 characters long.")
        password = getpass.getpass("Password: ")
    
    password_confirm = getpass.getpass("Confirm password: ")
    while password != password_confirm:
        print("Passwords don't match. Please try again.")
        password = getpass.getpass("Password: ")
        password_confirm = getpass.getpass("Confirm password: ")
    
    # Create the superuser
    try:
        user = User.objects.create_superuser(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        print(f"\nSuperuser created successfully!")
        print(f"ID: {user.id}")
        print(f"Email: {user.email}")
        print(f"Name: {user.first_name} {user.last_name}")
        return user
    except Exception as e:
        print(f"Error creating superuser: {e}")
        return None

def main():
    print("Django Superuser Management Tool")
    print("=" * 35)
    
    # Show current superusers
    superusers = User.objects.filter(is_superuser=True)
    print(f"\nCurrent superusers: {superusers.count()}")
    
    if superusers.exists():
        for user in superusers:
            print(f"  - {user.email} (ID: {user.id})")
    
    print("\nOptions:")
    print("1. Delete all existing superusers and create new one")
    print("2. Create new superuser (keep existing ones)")
    print("3. Delete all superusers only")
    print("4. Exit")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == '1':
        delete_all_superusers()
        create_new_superuser()
    elif choice == '2':
        create_new_superuser()
    elif choice == '3':
        delete_all_superusers()
    elif choice == '4':
        print("Exiting...")
    else:
        print("Invalid choice. Please run the script again.")

if __name__ == '__main__':
    main()