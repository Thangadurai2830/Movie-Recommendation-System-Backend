from rest_framework import serializers
from .models import Movie, Genre, Language, Country, Person, MovieCast, Rating, Watchlist
from django.contrib.auth import get_user_model
from django.db.models import Avg

User = get_user_model()

class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'name', 'description']

class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id', 'name', 'code']

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code']

class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ['id', 'name', 'birth_date', 'death_date', 'biography', 'profile_picture']

class MovieCastSerializer(serializers.ModelSerializer):
    person = PersonSerializer(read_only=True)
    person_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = MovieCast
        fields = ['id', 'person', 'person_id', 'role', 'character_name', 'order']

class MovieListSerializer(serializers.ModelSerializer):
    """Serializer for movie list view with basic information"""
    genres = GenreSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Movie
        fields = [
            'id', 'title', 'release_date', 'poster_url', 'genres',
            'duration', 'average_rating', 'rating_count', 'created_at'
        ]
    
    def get_average_rating(self, obj):
        avg_rating = obj.ratings.aggregate(avg=Avg('rating'))['avg']
        return round(avg_rating, 1) if avg_rating else None
    
    def get_rating_count(self, obj):
        return obj.ratings.count()

class MovieDetailSerializer(serializers.ModelSerializer):
    """Serializer for movie detail view with complete information"""
    genres = GenreSerializer(many=True, read_only=True)
    languages = LanguageSerializer(many=True, read_only=True)
    countries = CountrySerializer(many=True, read_only=True)
    cast = MovieCastSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    user_rating = serializers.SerializerMethodField()
    is_in_watchlist = serializers.SerializerMethodField()
    
    class Meta:
        model = Movie
        fields = [
            'id', 'title', 'overview', 'release_date', 'duration',
            'poster_url', 'backdrop_url', 'trailer_url', 'budget', 'revenue',
            'imdb_id', 'tmdb_id', 'imdb_rating', 'tmdb_rating',
            'genres', 'languages', 'countries', 'cast',
            'average_rating', 'rating_count', 'user_rating', 'is_in_watchlist',
            'created_at', 'updated_at'
        ]
    
    def get_average_rating(self, obj):
        avg_rating = obj.ratings.aggregate(avg=Avg('rating'))['avg']
        return round(avg_rating, 1) if avg_rating else None
    
    def get_rating_count(self, obj):
        return obj.ratings.count()
    
    def get_user_rating(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                rating = Rating.objects.get(user=request.user, movie=obj)
                return rating.rating
            except Rating.DoesNotExist:
                return None
        return None
    
    def get_is_in_watchlist(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Watchlist.objects.filter(user=request.user, movie=obj).exists()
        return False

class MovieCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating movies"""
    genre_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    language_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    country_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Movie
        fields = [
            'title', 'overview', 'release_date', 'duration',
            'poster_url', 'backdrop_url', 'trailer_url', 'budget', 'revenue',
            'imdb_id', 'tmdb_id', 'imdb_rating', 'tmdb_rating',
            'genre_ids', 'language_ids', 'country_ids'
        ]
    
    def create(self, validated_data):
        genre_ids = validated_data.pop('genre_ids', [])
        language_ids = validated_data.pop('language_ids', [])
        country_ids = validated_data.pop('country_ids', [])
        
        movie = Movie.objects.create(**validated_data)
        
        if genre_ids:
            movie.genres.set(genre_ids)
        if language_ids:
            movie.languages.set(language_ids)
        if country_ids:
            movie.countries.set(country_ids)
        
        return movie
    
    def update(self, instance, validated_data):
        genre_ids = validated_data.pop('genre_ids', None)
        language_ids = validated_data.pop('language_ids', None)
        country_ids = validated_data.pop('country_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if genre_ids is not None:
            instance.genres.set(genre_ids)
        if language_ids is not None:
            instance.languages.set(language_ids)
        if country_ids is not None:
            instance.countries.set(country_ids)
        
        return instance

class RatingSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    movie_title = serializers.CharField(source='movie.title', read_only=True)
    
    class Meta:
        model = Rating
        fields = ['id', 'user', 'movie', 'movie_title', 'rating', 'review', 'created_at', 'updated_at']
        read_only_fields = ['user']
    
    def validate_rating(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError("Rating must be between 1 and 10.")
        return value

class WatchlistSerializer(serializers.ModelSerializer):
    movie = MovieListSerializer(read_only=True)
    movie_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Watchlist
        fields = ['id', 'movie', 'movie_id', 'added_at']
        read_only_fields = ['user']

class MovieSearchSerializer(serializers.Serializer):
    """Serializer for movie search parameters"""
    query = serializers.CharField(required=False, allow_blank=True)
    genre = serializers.CharField(required=False, allow_blank=True)
    year = serializers.IntegerField(required=False, min_value=1900, max_value=2030)
    min_rating = serializers.FloatField(required=False, min_value=0, max_value=10)
    max_rating = serializers.FloatField(required=False, min_value=0, max_value=10)
    duration_min = serializers.IntegerField(required=False, min_value=1)
    duration_max = serializers.IntegerField(required=False, min_value=1)
    language = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)
    sort_by = serializers.ChoiceField(
        choices=['title', 'release_date', 'rating', 'duration', 'created_at'],
        required=False,
        default='created_at'
    )
    order = serializers.ChoiceField(
        choices=['asc', 'desc'],
        required=False,
        default='desc'
    )