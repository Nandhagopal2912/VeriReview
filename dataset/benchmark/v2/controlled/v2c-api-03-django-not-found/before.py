from django.http import JsonResponse

from shop.models import Product


def product_detail(request, pk):
    product = Product.objects.filter(pk=pk).first()
    return JsonResponse({"name": product.name})
