from django.urls import path
from .views import (
    GamePlayerListCreateView,
    GoalEventCreateView,
    GoalEventListByGameView,
)

urlpatterns = [
    path("games/<int:game_id>/players/",
         GamePlayerListCreateView.as_view(),
         name="game-players"),

    path("goals/",
         GoalEventCreateView.as_view(),
         name="goal-create"),

    path("games/<int:game_id>/goals/",
         GoalEventListByGameView.as_view(),
         name="game-goals"),
]
