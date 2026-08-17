#!/usr/bin/env python
"""
Test script for external API integration
Run this script to test TMDB and OMDB API connections
"""

import os
import sys
import django
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_recommendation.settings')
django.setup()

from movies.services import tmdb_service, omdb_service

def test_tmdb_connection():
    """Test TMDB API connection"""
    print("\n=== Testing TMDB API ===")
    
    # Test search
    print("Testing movie search...")
    search_results = tmdb_service.search_movies("The Matrix", 1)
    if search_results:
        print(f"✓ Search successful: Found {len(search_results.get('results', []))} movies")
        if search_results.get('results'):
            first_movie = search_results['results'][0]
            print(f"  First result: {first_movie.get('title')} ({first_movie.get('release_date', 'N/A')})")
    else:
        print("✗ Search failed")
    
    # Test popular movies
    print("\nTesting popular movies...")
    popular_results = tmdb_service.get_popular_movies(1)
    if popular_results:
        print(f"✓ Popular movies successful: Found {len(popular_results.get('results', []))} movies")
    else:
        print("✗ Popular movies failed")
    
    # Test trending movies
    print("\nTesting trending movies...")
    trending_results = tmdb_service.get_trending_movies('week', 1)
    if trending_results:
        print(f"✓ Trending movies successful: Found {len(trending_results.get('results', []))} movies")
    else:
        print("✗ Trending movies failed")
    
    # Test movie details (The Matrix - TMDB ID: 603)
    print("\nTesting movie details...")
    movie_details = tmdb_service.get_movie_details(603)
    if movie_details:
        print(f"✓ Movie details successful: {movie_details.get('title')} ({movie_details.get('release_date')})")
        print(f"  Runtime: {movie_details.get('runtime')} minutes")
        print(f"  Rating: {movie_details.get('vote_average')}/10")
    else:
        print("✗ Movie details failed")

def test_omdb_connection():
    """Test OMDB API connection"""
    print("\n=== Testing OMDB API ===")
    
    # Test movie by IMDB ID (The Matrix)
    print("Testing movie by IMDB ID...")
    movie_details = omdb_service.get_movie_by_imdb_id("tt0133093")
    if movie_details:
        print(f"✓ OMDB details successful: {movie_details.get('Title')} ({movie_details.get('Year')})")
        print(f"  Director: {movie_details.get('Director')}")
        print(f"  IMDB Rating: {movie_details.get('imdbRating')}/10")
    else:
        print("✗ OMDB details failed")
    
    # Test movie by title
    print("\nTesting movie search by title...")
    search_results = omdb_service.search_movies("Inception")
    if search_results:
        print(f"✓ OMDB search successful: Found {len(search_results.get('Search', []))} movies")
        if search_results.get('Search'):
            first_movie = search_results['Search'][0]
            print(f"  First result: {first_movie.get('Title')} ({first_movie.get('Year')})")
    else:
        print("✗ OMDB search failed")

def test_api_keys():
    """Test if API keys are configured"""
    print("=== Checking API Configuration ===")
    
    from django.conf import settings
    
    tmdb_key = getattr(settings, 'TMDB_API_KEY', None)
    omdb_key = getattr(settings, 'OMDB_API_KEY', None)
    
    if tmdb_key and tmdb_key != 'your_tmdb_api_key_here':
        print("✓ TMDB API key is configured")
    else:
        print("✗ TMDB API key is not configured or using placeholder")
        print("  Please set TMDB_API_KEY in your settings.py")
    
    if omdb_key and omdb_key != 'your_omdb_api_key_here':
        print("✓ OMDB API key is configured")
    else:
        print("✗ OMDB API key is not configured or using placeholder")
        print("  Please set OMDB_API_KEY in your settings.py")
    
    return bool(tmdb_key and tmdb_key != 'your_tmdb_api_key_here'), bool(omdb_key and omdb_key != 'your_omdb_api_key_here')

def main():
    """Main test function"""
    print("External API Integration Test")
    print("=============================")
    
    # Check API keys first
    tmdb_configured, omdb_configured = test_api_keys()
    
    if tmdb_configured:
        test_tmdb_connection()
    else:
        print("\nSkipping TMDB tests - API key not configured")
    
    if omdb_configured:
        test_omdb_connection()
    else:
        print("\nSkipping OMDB tests - API key not configured")
    
    print("\n=== Test Complete ===")
    if not tmdb_configured and not omdb_configured:
        print("\nTo enable external API features:")
        print("1. Get a free API key from https://www.themoviedb.org/settings/api")
        print("2. Get a free API key from http://www.omdbapi.com/apikey.aspx")
        print("3. Add them to your settings.py file")

if __name__ == '__main__':
    main()