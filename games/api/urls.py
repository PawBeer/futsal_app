from django.urls import path
from .views import GameRosterView, MatchSyncView

urlpatterns = [
    path("games/<int:game_id>/roster/", GameRosterView.as_view(), name="game-roster"),
    path("sync-match/", MatchSyncView.as_view(), name="match-sync"),
]
