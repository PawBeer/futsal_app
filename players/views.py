from django.shortcuts import render

from .models import Player


# Create your views here.
def all_players(request):
    found_players = Player.objects.all()
    return render(request, 'players/all_players.html', {'players': found_players})
