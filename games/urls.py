from django.urls import path
from . import views
urlpatterns = [
    path('', views.all_games, name='all_games_url'),
    path('<game_id>/', views.game_details, name='game_details_url'),
]