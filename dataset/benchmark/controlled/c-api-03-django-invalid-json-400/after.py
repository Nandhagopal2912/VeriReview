import json

from django.http import JsonResponse


def create_order(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)
    return JsonResponse({"id": data["id"]}, status=201)
