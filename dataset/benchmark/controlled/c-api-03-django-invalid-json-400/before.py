import json

from django.http import JsonResponse


def create_order(request):
    data = json.loads(request.body)
    return JsonResponse({"id": data["id"]}, status=201)
