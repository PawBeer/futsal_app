from rest_framework import serializers
from games.models import GoalEvent, GamePlayer

class GamePlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = GamePlayer
        fields = ["id", "game", "player", "team"]

class GoalEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalEvent
        fields = ["id", "game", "team", "scorer", "own_goal", "created_at"]
        read_only_fields = ["created_at"]
