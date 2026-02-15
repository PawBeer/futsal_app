from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from games.models import Game, Player, GoalEvent, BookingHistoryForGame, StatusChoices
from .serializers import GameRosterSerializer, BulkGameSyncSerializer


class GameRosterView(generics.ListAPIView):
    serializer_class = GameRosterSerializer

    def get_queryset(self):
        game_id = self.kwargs.get("game_id")

        latest_status_qs = BookingHistoryForGame.objects.filter(
            player=OuterRef("pk"), game_id=game_id
        ).order_by("-creation_date", "-id")

        return (
            Player.objects.annotate(
                current_status=Subquery(latest_status_qs.values("status")[:1])
            )
            .filter(current_status__in=[StatusChoices.PLANNED, StatusChoices.CONFIRMED])
            .distinct()
        )


class MatchSyncView(APIView):
    @transaction.atomic
    def post(self, request):
        serializer = BulkGameSyncSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            game = get_object_or_404(Game, id=data["game_id"])

            game.goals.all().delete()

            new_goals = []
            for g_data in data["goals"]:
                new_goals.append(
                    GoalEvent(
                        game=game,
                        team=g_data["team"],
                        scorer=g_data.get("scorer"),
                        own_goal=g_data.get("own_goal", False),
                        created_at=g_data["created_at"],
                    )
                )

            GoalEvent.objects.bulk_create(new_goals)

            game.status = data["status"]
            game.save()

            return Response(
                {
                    "status": "success",
                    "synced_goals": len(new_goals),
                    "game_status": game.status,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
