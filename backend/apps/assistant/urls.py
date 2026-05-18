from django.urls import path

from .views import NextActionsView

app_name = "assistant"

urlpatterns = [
    path("assistant/next-actions/", NextActionsView.as_view(), name="next-actions"),
]
