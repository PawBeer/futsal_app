from django.urls import path

from . import views

urlpatterns = [
    path("", views.settlement_overview, name="settlement_overview_url"),
    path("send/", views.send_settlement, name="send_settlement_url"),
    path(
        "charge/<int:charge_id>/toggle-paid/",
        views.toggle_paid,
        name="toggle_paid_url",
    ),
    path("who-paid/", views.who_paid, name="who_paid_url"),
]
