from django.shortcuts import render

# Create your views here.

from rest_framework import generics
from games.models import GamePlayer, GoalEvent
from .serializers import GamePlayerSerializer, GoalEventSerializer


class GamePlayerListCreateView(generics.ListCreateAPIView):
    serializer_class = GamePlayerSerializer

    def get_queryset(self):
        game_id = self.kwargs.get("game_id")
        return GamePlayer.objects.filter(game_id=game_id)


class GoalEventCreateView(generics.CreateAPIView):
    queryset = GoalEvent.objects.all()
    serializer_class = GoalEventSerializer


class GoalEventListByGameView(generics.ListAPIView):
    serializer_class = GoalEventSerializer

    def get_queryset(self):
        game_id = self.kwargs.get("game_id")
        return GoalEvent.objects.filter(game_id=game_id).order_by("created_at")
