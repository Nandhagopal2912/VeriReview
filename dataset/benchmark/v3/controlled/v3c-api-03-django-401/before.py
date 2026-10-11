from django.http import JsonResponse


def build_rows(month):
    return [{"month": month, "total": 0}]


def monthly_report(request, month):
    rows = build_rows(month)
    return JsonResponse({"rows": rows})
