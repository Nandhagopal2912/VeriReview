from django.http import HttpResponseNotFound, JsonResponse

from shop.models import Product


def product_detail(request, pk):
    product = Product.objects.filter(pk=pk).first()
    if product is None:
        return HttpResponseNotFound()
    return JsonResponse({"name": product.name})
