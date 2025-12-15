from django import forms
from django.contrib.auth import get_user_model

from .models import Player

User = get_user_model()


class PlayerProfileForm(forms.ModelForm):
    # they come from User model
    username = forms.CharField(required=True)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=True)
    # they come from Player model
    mobile_number = forms.CharField(required=True)
    role = forms.ChoiceField(choices=Player.ROLE_CHOICES, required=True)

    class Meta:
        model = Player
        exclude = ["user"]
        fields = ["mobile_number", "role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["username"].initial = self.instance.user.username
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        if self.instance and self.instance.user:
            player = super().save(commit=False)
            player.user.username = self.cleaned_data["username"]
            player.user.first_name = self.cleaned_data["first_name"]
            player.user.last_name = self.cleaned_data["last_name"]
            player.user.email = self.cleaned_data["email"]
            player.user.save()
            player.save()
            return player

        # new user and player
        user = get_user_model().objects.create_user(
            username=self.cleaned_data["username"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            email=self.cleaned_data["email"],
        )
        user.save()
        player = Player(
            user=user,
            mobile_number=self.cleaned_data["mobile_number"],
            role=self.cleaned_data["role"],
        )
        player.save()

        return player
