# api/serializers.py
from rest_framework import serializers
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from .models import (
    UserProfile,
    Trackable,
    TrackableLog,
    UserTrackable,
    SymptomLog,
    Symptom,
    UserSymptom
)

User = get_user_model()

class TrackableInputSerializer(serializers.Serializer):
    name = serializers.CharField()
    value_numeric = serializers.FloatField(required=False)
    value_text = serializers.CharField(required=False, allow_blank=True)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    trackables = TrackableInputSerializer(many=True, write_only=True, required=False)
    symptoms = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False
    )

    affiliated_user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True
    )

    average_cycle_length = serializers.IntegerField(required=False, default=28)
    last_period_sync = serializers.DateTimeField(required=False, allow_null=True)
    last_period_start = serializers.DateTimeField(required=False, allow_null=True)
    last_period_end = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "affiliated_user",
            "average_cycle_length",
            "last_period_sync",
            "last_period_start",
            "last_period_end",
            "trackables",
            "symptoms",
        )

    def create(self, validated_data):
        trackables_data = validated_data.pop("trackables", [])
        symptoms_data = validated_data.pop("symptoms", [])

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email"),
            password=validated_data["password"]
        )

        affiliated_user = validated_data.get("affiliated_user")
        if affiliated_user:
            user.affiliated_user = affiliated_user
            user.save()

        UserProfile.objects.create(
            user=user,
            average_cycle_length=validated_data.get("average_cycle_length", 28),
            last_period_sync=validated_data.get("last_period_sync"),
            last_period_start=validated_data.get("last_period_start"),
            last_period_end=validated_data.get("last_period_end"),
        )

        today = now().date()

        # Trackables
        for item in trackables_data:  
            trackable, _ = Trackable.objects.get_or_create(name=item["name"])
            print("🐞🐞 trackable added")

            UserTrackable.objects.get_or_create(user=user, trackable=trackable)

            if item.get("value_numeric") is not None or item.get("value_text"):
                TrackableLog.objects.update_or_create(
                    user=user,
                    trackable=trackable,
                    date=today,
                    defaults={
                        "value_numeric": item.get("value_numeric"),
                        "value_text": item.get("value_text", "")
                    }
                )

        # Symptoms
        for name in symptoms_data:
            symptom, _ = Symptom.objects.get_or_create(name=name)
            UserSymptom.objects.get_or_create(user=user, symptom=symptom)

        return user

class TrackableLogSerializer(serializers.ModelSerializer):
    trackables = TrackableInputSerializer(many=True, required=False)


    class Meta:
        model = TrackableLog
        fields = ("id", "trackable_name", "date", "value_numeric", "value_text")

    def create(self, validated_data):
        user = self.context["request"].user
        name = validated_data.pop("trackable_name")

        trackable = Trackable.objects.get(name=name)

        return TrackableLog.objects.update_or_create(
            user=user,
            trackable=trackable,
            date=validated_data["date"],
            defaults=validated_data
        )[0]
    

class SymptomLogSerializer(serializers.ModelSerializer):
    symptom_name = serializers.CharField(write_only=True)

    class Meta:
        model = SymptomLog
        fields = ("id", "symptom_name", "date", "severity", "notes")

    def create(self, validated_data):
        user = self.context["request"].user
        name = validated_data.pop("symptom_name")

        symptom = Symptom.objects.get(name=name)

        return SymptomLog.objects.update_or_create(
            user=user,
            symptom=symptom,
            date=validated_data["date"],
            defaults=validated_data
        )[0]
    
class TrackableLogCreateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='trackable.name', write_only=True)
    
    
    class Meta:
        model = TrackableLog
        fields = ('id', 'name', 'value_numeric', 'value_text')

    def create(self, validated_data):
        user = self.context['request'].user
        trackable_data = validated_data.pop('trackable')
        trackable_name = trackable_data['name']
        trackable, _ = Trackable.objects.get_or_create(name=trackable_name)
        today = now().date()

        log, _ = TrackableLog.objects.update_or_create(
            user=user,
            trackable=trackable,
            date= today,
            defaults={
                'value_numeric': validated_data.get('value_numeric'),
                'value_text': validated_data.get('value_text', ''),
            }
        )
        return log