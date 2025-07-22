from django.urls import path
from . import views
urlpatterns = [
    path('players/', views.all_players, name='all_players_url'),
    path('<player_id>/', views.player_details, name='player_details_url'),

]