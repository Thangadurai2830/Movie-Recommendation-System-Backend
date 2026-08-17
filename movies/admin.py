from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Avg, Count
from .models import Genre, Language, Country, Person, Movie, MovieCast, Rating, Watchlist

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'get_movie_count']
    search_fields = ['name']
    ordering = ['name']
    list_per_page = 25
    
    def get_movie_count(self, obj):
        count = obj.movies.count()
        if count > 0:
            url = reverse('admin:movies_movie_changelist') + f'?genres__id__exact={obj.id}'
            return format_html('<a href="{}">{} movies</a>', url, count)
        return "0 movies"
    get_movie_count.short_description = "Movies"

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'get_movie_count']
    search_fields = ['name', 'code']
    ordering = ['name']
    list_per_page = 25
    
    def get_movie_count(self, obj):
        count = obj.movies.count()
        return f"{count} movies"
    get_movie_count.short_description = "Movies"

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'get_movie_count']
    search_fields = ['name', 'code']
    ordering = ['name']
    list_per_page = 25
    
    def get_movie_count(self, obj):
        count = obj.movies.count()
        return f"{count} movies"
    get_movie_count.short_description = "Movies"

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'birth_date', 'birth_place', 'get_movie_count', 'created_at']
    search_fields = ['name', 'birth_place']
    list_filter = ['birth_place', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'biography')
        }),
        ('Personal Details', {
            'fields': ('birth_date', 'death_date', 'birth_place')
        }),
        ('Media', {
            'fields': ('profile_image',)
        }),
        ('External IDs', {
            'fields': ('tmdb_id', 'imdb_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_movie_count(self, obj):
        count = obj.cast_movies.count()
        return f"{count} movies"
    get_movie_count.short_description = "Movies"

class MovieCastInline(admin.TabularInline):
    model = MovieCast
    extra = 1
    autocomplete_fields = ['person']
    fields = ['person', 'character_name', 'order']

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = [
        'get_poster_thumbnail', 'title', 'year', 'duration', 
        'get_average_rating', 'get_rating_count', 'status', 'created_at'
    ]
    search_fields = ['title', 'original_title', 'overview']
    list_filter = ['status', 'year', 'genres', 'languages', 'created_at']
    filter_horizontal = ['genres', 'languages', 'countries']
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = []
    readonly_fields = [
        'created_at', 'updated_at', 'get_average_rating', 
        'get_rating_count', 'get_poster_display'
    ]
    inlines = [MovieCastInline]
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'original_title', 'slug', 'overview')
        }),
        ('Movie Details', {
            'fields': ('year', 'duration', 'status', 'adult')
        }),
        ('Classifications', {
            'fields': ('genres', 'languages', 'countries')
        }),
        ('Media', {
            'fields': ('poster_path', 'backdrop_path', 'get_poster_display')
        }),
        ('External Data', {
            'fields': ('tmdb_id', 'imdb_id', 'budget', 'revenue'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('get_average_rating', 'get_rating_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_poster_thumbnail(self, obj):
        if obj.poster_path:
            return format_html(
                '<img src="{}" style="width: 40px; height: 60px; object-fit: cover; border-radius: 4px;"/>',
                obj.poster_path
            )
        return "No poster"
    get_poster_thumbnail.short_description = "Poster"
    
    def get_poster_display(self, obj):
        if obj.poster_path:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 300px; object-fit: cover; border-radius: 8px;"/>',
                obj.poster_path
            )
        return "No poster available"
    get_poster_display.short_description = "Poster Preview"
    
    def get_average_rating(self, obj):
        avg_rating = obj.ratings.aggregate(avg=Avg('rating'))['avg']
        if avg_rating:
            stars = "⭐" * int(avg_rating)
            return f"{round(avg_rating, 2)} {stars}"
        return 'No ratings'
    get_average_rating.short_description = 'Average Rating'
    
    def get_rating_count(self, obj):
        count = obj.ratings.count()
        if count > 0:
            url = reverse('admin:movies_rating_changelist') + f'?movie__id__exact={obj.id}'
            return format_html('<a href="{}">{} ratings</a>', url, count)
        return "No ratings"
    get_rating_count.short_description = "Total Ratings"

@admin.register(MovieCast)
class MovieCastAdmin(admin.ModelAdmin):
    list_display = ['movie', 'person', 'role', 'character_name']
    search_fields = ['movie__title', 'person__name', 'character_name']
    list_filter = ['role']
    autocomplete_fields = ['movie', 'person']

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_movie_title', 'get_rating_display', 'review_excerpt', 'created_at']
    search_fields = ['user__username', 'movie__title', 'review']
    list_filter = ['rating', 'created_at']
    autocomplete_fields = ['user', 'movie']
    ordering = ['-created_at']
    list_per_page = 25
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Rating Information', {
            'fields': ('user', 'movie', 'rating')
        }),
        ('Review', {
            'fields': ('review',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_movie_title(self, obj):
        return obj.movie.title
    get_movie_title.short_description = "Movie"
    get_movie_title.admin_order_field = 'movie__title'
    
    def get_rating_display(self, obj):
        stars = "⭐" * int(obj.rating)
        return f"{obj.rating} {stars}"
    get_rating_display.short_description = "Rating"
    get_rating_display.admin_order_field = 'rating'
    
    def review_excerpt(self, obj):
        if obj.review:
            return obj.review[:100] + "..." if len(obj.review) > 100 else obj.review
        return "No review"
    review_excerpt.short_description = "Review Excerpt"

@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_movie_title', 'get_movie_year', 'get_movie_rating', 'added_at']
    search_fields = ['user__username', 'movie__title']
    list_filter = ['added_at', 'movie__year']
    autocomplete_fields = ['user', 'movie']
    ordering = ['-added_at']
    list_per_page = 25
    
    def get_movie_title(self, obj):
        return obj.movie.title
    get_movie_title.short_description = "Movie"
    get_movie_title.admin_order_field = 'movie__title'
    
    def get_movie_year(self, obj):
        return obj.movie.year
    get_movie_year.short_description = "Year"
    get_movie_year.admin_order_field = 'movie__year'
    
    def get_movie_rating(self, obj):
        avg_rating = obj.movie.ratings.aggregate(avg=Avg('rating'))['avg']
        if avg_rating:
            return f"{round(avg_rating, 1)} ⭐"
        return "No ratings"
    get_movie_rating.short_description = "Movie Rating"
