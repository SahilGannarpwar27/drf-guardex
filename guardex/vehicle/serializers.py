from .models import Tractor, Trailer, Trip
from rest_framework import serializers

class TractorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tractor
        fields = '__all__'
        
    def validate_tractor_id(self, value):
        prefix = Tractor.PREFIX 
        
        if not value.startswith(prefix):
            return f"{prefix}{value}"
            
        return value
        
class TrailerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trailer
        fields = '__all__'
        
    def validate_trailer_id(self, value):
        prefix = Trailer.PREFIX 
        
        if not value.startswith(prefix):
            return f"{prefix}{value}"
            
        return value
    
class TripSerializer(serializers.ModelSerializer):
    tractor = serializers.PrimaryKeyRelatedField(
        queryset=Tractor.objects.all()
    )
    
    trailer = serializers.PrimaryKeyRelatedField(
        queryset=Trailer.objects.all(),
        many=True,
        allow_empty=False,
        error_messages={
            'empty': 'At least one trailer is required.'
        }
    )    
    
    class Meta:
        model = Trip
        fields = '__all__'
          
    def validate_trip_id(self, value):
        prefix = Trip.PREFIX 
        
        if not value.startswith(prefix):
            return f"{prefix}{value}"
            
        return value
    
    def validate_trailer(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate trailers are not allowed."
            )

        return value
    
    def validate(self, attrs):
        tractor = attrs.get("tractor")
        trailers = attrs.get("trailer", [])

        if tractor.status.lower() != "idle":
            raise serializers.ValidationError({
                "tractor": f"Tractor '{tractor}' is not idle."
            })

        non_idle_trailers = [
            trailer.trailer_id
            for trailer in trailers
            if trailer.status.lower() != "idle"
        ]

        if non_idle_trailers:
            raise serializers.ValidationError({
                "trailer": (
                    f"These trailers are not idle: "
                    f"{', '.join(non_idle_trailers)}"
                )
            })

        return attrs
    
    # def create(self, validated_data):
    #     trailers_data = validated_data.pop('trailer', [])
    #     trip = Trip.objects.create(**validated_data)
    #     for trailer in trailers_data:
    #         trailerobj = Trailer.objects.get(trailer_id=trailer)  # Ensure the trailer exists
    #         TripTrailerRel.objects.create(trip=trip, trailer=trailerobj)
    #     # trip.trailer.add(*trailers_data)
    #     return trip