
# Movie Recommendation System API Documentation

## Overview

The Movie Recommendation System provides a comprehensive REST API for movie recommendations, user preferences, interactions, and feedback. This API uses machine learning algorithms to deliver personalized movie suggestions.

## Base URL

```
http://localhost:8000/api/
```

## Authentication

The API uses Token-based authentication. Include the token in the Authorization header:

```
Authorization: Token your_token_here
```

### Obtaining a Token

**POST** `/auth/login/`

```json
{
    "username": "your_username",
    "password": "your_password"
}
```

**Response:**
```json
{
    "token": "your_auth_token",
    "user_id": 1,
    "username": "your_username"
}
```

## Content Type
All requests should use `application/json` content type.

---

## Authentication Endpoints

### POST /api/auth/register/
Register a new user account.

**Request Body:**
```json
{
    "username": "string",
    "email": "string",
    "password": "string",
    "first_name": "string",
    "last_name": "string",
    "date_of_birth": "YYYY-MM-DD"
}
```

**Response (201 Created):**
```json
{
    "user": {
        "id": 1,
        "username": "string",
        "email": "string",
        "first_name": "string",
        "last_name": "string"
    },
    "access": "jwt_access_token",
    "refresh": "jwt_refresh_token"
}
```

### POST /api/auth/login/
Authenticate user and get JWT tokens.

**Request Body:**
```json
{
    "username": "string",
    "password": "string"
}
```

**Response (200 OK):**
```json
{
    "access": "jwt_access_token",
    "refresh": "jwt_refresh_token",
    "user": {
        "id": 1,
        "username": "string",
        "email": "string"
    }
}
```

### POST /api/auth/refresh/
Refresh JWT access token.

**Request Body:**
```json
{
    "refresh": "jwt_refresh_token"
}
```

**Response (200 OK):**
```json
{
    "access": "new_jwt_access_token"
}
```

---

## User Management Endpoints

### GET /api/users/profile/
Get current user's profile information.

**Headers:** `Authorization: Bearer <token>`

**Response (200 OK):**
```json
{
    "id": 1,
    "username": "string",
    "email": "string",
    "first_name": "string",
    "last_name": "string",
    "date_of_birth": "YYYY-MM-DD",
    "bio": "string",
    "profile_picture": "url",
    "favorite_genres": ["Action", "Drama"],
    "preferred_languages": ["en", "es"]
}
```

### PUT /api/users/profile/
Update current user's profile.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
    "first_name": "string",
    "last_name": "string",
    "bio": "string",
    "favorite_genres": ["Action", "Drama"],
    "preferred_languages": ["en", "es"]
}
```

---

## Movie Endpoints

### GET /api/movies/
Get list of movies with filtering and pagination.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)
- `search`: Search in title and overview
- `genre`: Filter by genre name
- `year`: Filter by release year
- `min_rating`: Minimum average rating
- `ordering`: Sort by field (title, release_date, average_rating, -title, etc.)

**Response (200 OK):**
```json
{
    "count": 1000,
    "next": "http://localhost:8000/api/movies/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "title": "The Matrix",
            "original_title": "The Matrix",
            "overview": "Movie description...",
            "release_date": "1999-03-31",
            "runtime": 136,
            "poster_url": "https://image.tmdb.org/...",
            "backdrop_url": "https://image.tmdb.org/...",
            "average_rating": 8.7,
            "rating_count": 1500,
            "genres": ["Action", "Sci-Fi"],
            "languages": ["English"]
        }
    ]
}
```

### GET /api/movies/{id}/
Get detailed information about a specific movie.

**Response (200 OK):**
```json
{
    "id": 1,
    "title": "The Matrix",
    "original_title": "The Matrix",
    "overview": "Movie description...",
    "tagline": "Welcome to the Real World",
    "release_date": "1999-03-31",
    "year": 1999,
    "runtime": 136,
    "budget": 63000000,
    "revenue": 467222824,
    "poster_url": "https://image.tmdb.org/...",
    "backdrop_url": "https://image.tmdb.org/...",
    "average_rating": 8.7,
    "rating_count": 1500,
    "tmdb_rating": 8.2,
    "popularity": 85.5,
    "adult": false,
    "genres": [
        {"id": 1, "name": "Action"},
        {"id": 2, "name": "Sci-Fi"}
    ],
    "languages": [
        {"id": 1, "name": "English", "code": "en"}
    ],
    "countries": [
        {"id": 1, "name": "United States", "code": "US"}
    ],
    "cast": [
        {
            "id": 1,
            "name": "Keanu Reeves",
            "character": "Neo",
            "order": 0
        }
    ],
    "crew": [
        {
            "id": 2,
            "name": "Lana Wachowski",
            "job": "Director",
            "department": "Directing"
        }
    ]
}
```

### POST /api/movies/
Create a new movie (Admin only).

**Headers:** `Authorization: Bearer <admin_token>`

### PUT /api/movies/{id}/
Update a movie (Admin only).

### DELETE /api/movies/{id}/
Delete a movie (Admin only).

---

## Rating Endpoints

### GET /api/movies/{movie_id}/ratings/
Get ratings for a specific movie.

**Response (200 OK):**
```json
{
    "count": 150,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "user": {
                "id": 1,
                "username": "john_doe"
            },
            "rating": 9,
            "review": "Amazing movie!",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z"
        }
    ]
}
```

### POST /api/movies/{movie_id}/rate/
Rate a movie.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
    "rating": 9,
    "review": "Amazing movie!"
}
```

### PUT /api/ratings/{id}/
Update your rating.

### DELETE /api/ratings/{id}/
Delete your rating.

---

## Recommendation Endpoints

### GET /api/recommendations/
Get personalized movie recommendations.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `page`: Page number
- `algorithm`: Recommendation algorithm (collaborative, content_based, hybrid)
- `limit`: Number of recommendations (default: 10, max: 50)

**Response (200 OK):**
```json
{
    "count": 25,
    "results": [
        {
            "movie": {
                "id": 1,
                "title": "The Matrix",
                "poster_url": "https://image.tmdb.org/...",
                "average_rating": 8.7
            },
            "confidence_score": 0.95,
            "algorithm_used": "collaborative_filtering",
            "reason": "Users who liked similar movies also enjoyed this"
        }
    ]
}
```

### POST /api/recommendations/{id}/feedback/
Provide feedback on a recommendation.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
    "feedback_type": "like",  // "like", "dislike", "not_interested"
    "comment": "Great recommendation!"
}
```

---

## Watchlist Endpoints

### GET /api/movies/watchlist/
Get user's watchlist.

**Headers:** `Authorization: Bearer <token>`

### POST /api/movies/{movie_id}/toggle-watchlist/
Add or remove movie from watchlist.

**Headers:** `Authorization: Bearer <token>`

**Response (200 OK):**
```json
{
    "added": true,
    "message": "Movie added to watchlist"
}
```

---

## External API Integration Endpoints

### GET /api/movies/tmdb/search/
Search movies using TMDB API.

**Query Parameters:**
- `q`: Search query (required)
- `page`: Page number

**Response (200 OK):**
```json
{
    "page": 1,
    "total_pages": 10,
    "total_results": 200,
    "results": [
        {
            "id": 603,
            "title": "The Matrix",
            "overview": "...",
            "release_date": "1999-03-31",
            "poster_path": "/path/to/poster.jpg",
            "vote_average": 8.2
        }
    ]
}
```

### GET /api/movies/tmdb/popular/
Get popular movies from TMDB.

### GET /api/movies/tmdb/trending/
Get trending movies from TMDB.

**Query Parameters:**
- `time_window`: "day" or "week" (default: "week")
- `page`: Page number

### GET /api/movies/tmdb/movie/{tmdb_id}/
Get detailed movie information from TMDB.

### GET /api/movies/tmdb/movie/{tmdb_id}/recommendations/
Get movie recommendations from TMDB.

### GET /api/movies/tmdb/movie/{tmdb_id}/similar/
Get similar movies from TMDB.

### GET /api/movies/omdb/movie/{imdb_id}/
Get movie details from OMDB by IMDB ID.

### POST /api/movies/import/tmdb/
Import a movie from TMDB into the database.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
    "tmdb_id": 603
}
```

---

## Statistics Endpoints

### GET /api/movies/stats/
Get movie statistics.

**Response (200 OK):**
```json
{
    "total_movies": 1000,
    "total_genres": 20,
    "total_ratings": 5000,
    "average_rating": 7.2,
    "movies_by_year": [
        {"year": 2023, "count": 150},
        {"year": 2022, "count": 200}
    ],
    "top_genres": [
        {"name": "Action", "movie_count": 250},
        {"name": "Drama", "movie_count": 200}
    ]
}
```

---

## Error Responses

### 400 Bad Request
```json
{
    "error": "Invalid request data",
    "details": {
        "field_name": ["This field is required."]
    }
}
```

### 401 Unauthorized
```json
{
    "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
    "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
    "detail": "Not found."
}
```

### 500 Internal Server Error
```json
{
    "error": "Internal server error",
    "message": "An unexpected error occurred."
}
```

---

## Rate Limiting
- Anonymous users: 100 requests per hour
- Authenticated users: 1000 requests per hour
- Admin users: 5000 requests per hour

## Pagination
All list endpoints support pagination with the following parameters:
- `page`: Page number (starts from 1)
- `page_size`: Items per page (default: 20, max: 100)

## Filtering and Searching
Most list endpoints support filtering and searching:
- Use query parameters for filtering
- Use `search` parameter for text search
- Use `ordering` parameter for sorting (prefix with `-` for descending)

## External API Configuration
To use external API features, configure the following in your settings:
```python
TMDB_API_KEY = 'your_tmdb_api_key'
OMDB_API_KEY = 'your_omdb_api_key'
```

Get API keys from:
- TMDB: https://www.themoviedb.org/settings/api
- OMDB: http://www.omdbapi.com/apikey.aspx

---

## Testing
Use the Django REST framework browsable API at `/api/` for interactive testing.

For automated testing, run:
```bash
python manage.py test
```

For external API testing:
```bash
python test_external_apis.py
```
