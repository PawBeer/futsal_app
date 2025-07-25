from django.shortcuts import render, redirect
from member.forms import RegisterForm
from games.models import Player

# Create your views here.
def register(request):
    if request.method == 'GET':
        form = RegisterForm()
        return render(request,'members/register.html',{
            'form':form
        })

    form = RegisterForm(request.POST)
    if form.is_valid():
        user = form.save(commit=False)
        user.username = user.username.lower()
        user.save()
        Player.objects.create(
            user=user,
            nickname=form.cleaned_data['nickname'],
            mobile_number=form.cleaned_data['mobile_number']
        )
        return redirect('login')
    else:
        return render(request,'members/register.html',{
            'form':form
        })