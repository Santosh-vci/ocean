from django.urls import path

from .views import ActiveFlowView, FlowRunDetailView, FlowRunEventView

urlpatterns = [
    path("flows/active/", ActiveFlowView.as_view(), name="flow-active"),
    path("flows/<str:run_id>/", FlowRunDetailView.as_view(), name="flow-detail"),
    path("flows/<str:run_id>/events/", FlowRunEventView.as_view(), name="flow-events"),
]
