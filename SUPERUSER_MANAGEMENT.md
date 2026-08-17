# Django Superuser Management Guide

This guide explains how to manage superusers in your Movie Recommendation System.

## Current Database Status

**Current Superuser:**
- ID: 1
- Email: admin@example.com
- Name: Admin User
- Status: Active
- Created: 2025-08-27

## Management Tools Available

### 1. Interactive Management Script

**File:** `manage_superuser.py`

**Usage:**
```bash
python manage_superuser.py
```

**Features:**
- Interactive menu-driven interface
- View current superusers
- Delete all superusers
- Create new superuser with prompts
- Password confirmation
- Input validation

### 2. Command Line Management Script

**File:** `create_superuser.py`

**Usage:**
```bash
# List all superusers
python create_superuser.py list

# Create a new superuser
python create_superuser.py create <email> <password> [first_name] [last_name]

# Delete a superuser
python create_superuser.py delete <email>
```

**Examples:**
```bash
# List current superusers
python create_superuser.py list

# Create a new superuser
python create_superuser.py create admin@movie.com mypassword123 John Doe

# Delete existing superuser
python create_superuser.py delete admin@example.com
```

### 3. Django Built-in Command

**Usage:**
```bash
python manage.py createsuperuser
```

## Step-by-Step: Replace Current Superuser

### Option A: Using Command Line Script

1. **Delete existing superuser:**
   ```bash
   python create_superuser.py delete admin@example.com
   ```

2. **Create new superuser:**
   ```bash
   python create_superuser.py create your-email@domain.com your-password Your-FirstName Your-LastName
   ```

3. **Verify creation:**
   ```bash
   python create_superuser.py list
   ```

### Option B: Using Interactive Script

1. **Run interactive script:**
   ```bash
   python manage_superuser.py
   ```

2. **Choose option 1:** "Delete all existing superusers and create new one"

3. **Follow the prompts** to enter your details

### Option C: Using Django Command

1. **Delete existing superuser first:**
   ```bash
   python create_superuser.py delete admin@example.com
   ```

2. **Create new superuser:**
   ```bash
   python manage.py createsuperuser
   ```

## Quick Commands for You

**To delete current superuser and create a new one:**

```bash
# Navigate to backend directory
cd backend

# Delete current superuser
python create_superuser.py delete admin@example.com

# Create your new superuser (replace with your details)
python create_superuser.py create youremail@domain.com yourpassword123 YourFirstName YourLastName

# Verify the new superuser
python create_superuser.py list
```

## Security Notes

1. **Strong Passwords:** Use passwords with at least 8 characters, including uppercase, lowercase, numbers, and special characters.

2. **Email Validation:** The system uses email as the username field, so ensure you use a valid email address.

3. **Database Backup:** Consider backing up your database before making changes to superuser accounts.

4. **Environment Variables:** For production, consider storing superuser credentials in environment variables.

## Troubleshooting

### Database Issues
If you encounter database errors:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Permission Issues
Ensure you're in the correct directory and have proper permissions:
```bash
cd backend
ls -la  # Check file permissions
```

### API Key Warnings
The "TMDB API key not found" warnings are normal and don't affect superuser management.

## Files Created

- `check_superusers.py` - View current superusers
- `manage_superuser.py` - Interactive management
- `create_superuser.py` - Command-line management
- `SUPERUSER_MANAGEMENT.md` - This documentation

All files are located in the `backend/` directory.