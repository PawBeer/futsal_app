from django.urls import path
from . import views
urlpatterns = [
    path('', views.next_games, name='next_games_url'),
    path('past/', views.past_games, name='past_games_url'),
    path('game/<game_id>/', views.game_details, name='game_details_url'),
    path('players/', views.all_players, name='all_players_url'),
    path('players/<player_id>/', views.player_details, name='player_details_url'),
    path('add_player', views.add_player, name='add_player_url'),
    path('add_player_with_form', views.add_player_with_form, name='add_player_with_form_url'),
    path('booking_history/', views.booking_history, name='booking_history_url'),
]