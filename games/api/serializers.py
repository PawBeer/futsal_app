from rest_framework import serializers
from games.models import GoalEvent, Player, Game, GameStatus, StatusChoices


class GameRosterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="__str__", read_only=True)

    class Meta:
        model = Player
        fields = ["id", "name", "mobile_number", "role"]


class GoalSyncSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField()

    class Meta:
        model = GoalEvent
        fields = ["team", "scorer", "own_goal", "created_at"]


class BulkGameSyncSerializer(serializers.Serializer):
    game_id = serializers.IntegerField()
    goals = GoalSyncSerializer(many=True)
    status = serializers.ChoiceField(
        choices=GameStatus.choices, default=GameStatus.PLAYED
    )
