# api/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    # Password should never be returned
    password = serializers.CharField(write_only=True)
    
    # Optional affiliated_user: must reference an existing user if provided
    affiliated_user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = User
        fields = ('id','username', 'email', 'password', 'affiliated_user')

    def create(self, validated_data):
        # Pop affiliated_user if present
        affiliated_user = validated_data.pop('affiliated_user', None)

        # Create the user with Django's create_user() to hash the password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email'),
            password=validated_data['password']
        )

        # Assign affiliated_user if provided
        if affiliated_user:
            user.affiliated_user = affiliated_user
            user.save()

        return user
