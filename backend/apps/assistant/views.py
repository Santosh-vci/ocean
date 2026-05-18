from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import NextActionsResponseSerializer
from .services import get_next_actions


class NextActionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = get_next_actions(
            user=request.user,
            route=request.query_params.get("route"),
            object_type=request.query_params.get("object_type"),
            object_id=request.query_params.get("object_id"),
            mode=request.query_params.get("mode") or "assisted",
            limit=_parse_limit(request.query_params.get("limit")),
        )
        return Response(NextActionsResponseSerializer(payload).data)


def _parse_limit(raw_limit: str | None) -> int:
    if raw_limit is None:
        return 10
    try:
        return int(raw_limit)
    except (TypeError, ValueError):
        return 10
