from django.urls import path
from . import views
urlpatterns = [
    path('', views.next_games, name='next_games_url'),
    path('past/', views.past_games, name='past_games_url'),
    path('<game_id>/', views.game_details, name='game_details_url'),
]