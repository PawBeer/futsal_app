from django import forms
from django.contrib.auth.models import User
from .models import Player


class PlayerProfileForm(forms.ModelForm):
    username = forms.CharField(required=True)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=True)
    mobile_number = forms.CharField(required=True)

    class Meta:
        model = Player
        fields = ["role"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["username"].initial = self.instance.user.username
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def save(self, commit=True):
        player = super().save(commit=False)

        # Update User model fields
        if player.user:
            player.user.username = self.cleaned_data["username"]
            player.user.first_name = self.cleaned_data["first_name"]
            player.user.last_name = self.cleaned_data["last_name"]
            player.user.email = self.cleaned_data["email"]
            if commit:
                player.user.save()

        # Update Player model fields
        player.mobile_number = self.cleaned_data["mobile_number"]
        if commit:
            player.save()

        return player
