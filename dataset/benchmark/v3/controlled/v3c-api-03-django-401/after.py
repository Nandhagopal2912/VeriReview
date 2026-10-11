from django.http import JsonResponse


def build_rows(month):
    return [{"month": month, "total": 0}]


def monthly_report(request, month):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "login required"}, status=401)
    rows = build_rows(month)
    return JsonResponse({"rows": rows})
