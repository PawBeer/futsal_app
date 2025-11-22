from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.next_games, name="next_games_url"),
    path("past/", views.past_games, name="past_games_url"),
    path("game/<game_id>/", views.game_details, name="game_details_url"),
    path("game/<game_id>/remove", views.game_remove, name="game_remove_url"),
    path(
        "game/<int:game_id>/update-status/",
        views.game_status_update,
        name="game_status_update_url",
    ),
    path(
        "game/<int:game_id>/update-player-status/",
        views.game_player_status_update,
        name="game_player_status_update_url",
    ),
    path("players/", views.all_players, name="all_players_url"),
    path("players/<player_id>/", views.player_details, name="player_details_url"),
    path("add_player", views.add_player, name="add_player_url"),
    path("add_game", views.add_game, name="add_game_url"),
    path("add_absence", views.add_absence, name="add_absence_url"),
    path("booking_history/", views.booking_history, name="booking_history_url"),
    path("logout/", LogoutView.as_view(next_page="/accounts/login"), name="logout_url"),
    path("login/", LoginView.as_view(next_page="next_games_url"), name="login_url"),
    path(
        "ajax/check_username_and_email/",
        views.check_username_and_email,
        name="check_username_and_email",
    ),
]
