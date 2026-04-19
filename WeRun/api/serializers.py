# api/serializers.py
from rest_framework import serializers
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from .utils import get_user_cycle_context
from .models import (
    UserProfile,
    Trackable,
    TrackableLog,
    UserTrackable,
    SymptomLog,
    Symptom,
    UserSymptom,
    Cycle,
    CycleSampleLog
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

class SymptomLogWriteSerializer(serializers.ModelSerializer):
    symptom = serializers.PrimaryKeyRelatedField(
        queryset=Symptom.objects.all()
    )
    date = serializers.DateField()

    class Meta:
        model = SymptomLog
        fields = ["id", "symptom", "date"]
    
    def create(self, validated_data):
        # Attach the current user automatically
        user = self.context['request'].user
        return SymptomLog.objects.create(user=user, **validated_data)
    
    
    
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
    
class CycleSampleLogCreateSerializer(serializers.ModelSerializer):


    
    cycle_id = serializers.UUIDField(write_only=True)
    symptoms = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = CycleSampleLog
        fields = (
            "id",
            "cycle_id",
            "date_logged",
            "day_of_cycle",
            "flow_type",
            "notes",
            "symptoms",
        )

    def create(self, validated_data):
        user = self.context["request"].user
        cycle_id = validated_data.pop("cycle_id")
        symptom_names = validated_data.pop("symptoms", [])

        cycle = Cycle.objects.get(id=cycle_id, user=user)

        log, _ = CycleSampleLog.objects.update_or_create(
            user=user,
            cycle=cycle,
            date_logged=validated_data["date_logged"],
            day_of_cycle=validated_data["day_of_cycle"],
            defaults={
                "flow_type": validated_data.get("flow_type"),
                "notes": validated_data.get("notes", ""),
            },
        )

        # Handle symptoms
        if symptom_names:
            symptoms = []
            for name in symptom_names:
                symptom, _ = Symptom.objects.get_or_create(name=name)
                symptoms.append(symptom)

            log.symptoms.set(symptoms)

        return log

class CycleDayLogCreateSerializer(serializers.Serializer):
    cycle_id = serializers.UUIDField()
    date_logged = serializers.DateField()
    flow_type = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True)
    symptoms = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )

# READ ONLY SERIALISERS FOR RETURNING ALL USER DATA --------------------

class TrackableLogSerializer(serializers.ModelSerializer):
    unit = serializers.CharField(source="trackable.unit", read_only=True)
    name = serializers.CharField(source="trackable.name")

    phase = serializers.SerializerMethodField()
    cycle_day = serializers.SerializerMethodField()


    class Meta:
        model = TrackableLog
        fields = (
            "id",
            "name",
            "date",
            "value_numeric",
            "value_text",
            "unit",
            "phase",
            "cycle_day",
        )
    
    def get_phase(self, obj):
        phase, _ = get_user_cycle_context(user=obj.user, target_date=obj.date)
        return phase

    def get_cycle_day(self, obj):
        _, cycle_day = get_user_cycle_context(user=obj.user, target_date=obj.date)
        return cycle_day

class SymptomLogSerializer(serializers.ModelSerializer):
    symptom_name = serializers.CharField(source="symptom.name")
    phase = serializers.SerializerMethodField()
    cycle_day = serializers.SerializerMethodField()

    class Meta:
        model = SymptomLog
        fields = ("id", "symptom_name", "date", "phase", "cycle_day", "notes")

    def get_phase(self, obj):
        phase, _ = get_user_cycle_context(user=obj.user, target_date=obj.date)
        return phase

    def get_cycle_day(self, obj):
        _, cycle_day = get_user_cycle_context(user=obj.user, target_date=obj.date)
        return cycle_day

class CycleSampleLogSerializer(serializers.ModelSerializer):
    symptoms = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field="name"
    )

    class Meta:
        model = CycleSampleLog
        fields = (
            "id",
            "date_logged",
            "flow_type",
            "notes",
            "symptoms",
        )

class CycleSerializer(serializers.ModelSerializer):
    samples = CycleSampleLogSerializer(many=True, read_only=True)

    class Meta:
        model = Cycle
        fields = (
            "id",
            "period_start_date",
            "period_end_date",
            "notes",
            "samples",
        )

class UserTrackingDashboardSerializer(serializers.Serializer):
    trackables = TrackableLogSerializer(many=True)
    symptoms = SymptomLogSerializer(many=True)
    cycles = CycleSerializer(many=True)