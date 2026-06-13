from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import Min, Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Product


SORT_CHOICES = [
    ('featured', 'Featured'),
    ('price_asc', 'Price: low to high'),
    ('price_desc', 'Price: high to low'),
    ('newest', 'Newest'),
    ('name', 'Name: A–Z'),
]
SORT_KEYS = {key for key, _ in SORT_CHOICES}


def _parse_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def product_list(request):
    # Base queryset with efficiency annotations.
    qs = (
        Product.objects.filter(is_active=True)
        .select_related('category')
        .prefetch_related('variants')
        .annotate(min_price=Min('variants__price', filter=Q(variants__is_active=True)))
    )

    # ----- Filters from GET -----
    category_slugs = request.GET.getlist('category')
    if category_slugs:
        qs = qs.filter(category__slug__in=category_slugs)

    min_price = _parse_decimal(request.GET.get('min_price'))
    if min_price is not None:
        qs = qs.filter(min_price__gte=min_price)

    max_price = _parse_decimal(request.GET.get('max_price'))
    if max_price is not None:
        qs = qs.filter(min_price__lte=max_price)

    in_stock_only = request.GET.get('in_stock') == 'on'
    if in_stock_only:
        qs = qs.filter(
            variants__is_active=True,
            variants__stock_quantity__gt=0,
        ).distinct()

    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(short_description__icontains=q)
            | Q(description__icontains=q)
        )

    # ----- Sort -----
    sort = request.GET.get('sort', 'featured')
    if sort not in SORT_KEYS:
        sort = 'featured'
    if sort == 'price_asc':
        qs = qs.order_by('min_price', 'display_order', 'name')
    elif sort == 'price_desc':
        qs = qs.order_by('-min_price', 'display_order', 'name')
    elif sort == 'newest':
        qs = qs.order_by('-created_at', 'name')
    elif sort == 'name':
        qs = qs.order_by('name')
    else:  # featured
        qs = qs.order_by('-is_featured', 'display_order', 'name')

    # ----- Paginate -----
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = Category.objects.filter(is_active=True).order_by('display_order', 'name')

    # Build a fresh querystring (everything except `page`) so the pagination
    # partial doesn't have to special-case anything.
    qs_dict = request.GET.copy()
    qs_dict.pop('page', None)

    return render(request, 'catalog/product_list.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'products': page_obj.object_list,
        'categories': categories,
        'sort_choices': SORT_CHOICES,
        # Echo current filter values back so the form preserves state.
        'selected_categories': category_slugs,
        'q': q,
        'min_price': request.GET.get('min_price', ''),
        'max_price': request.GET.get('max_price', ''),
        'in_stock_only': in_stock_only,
        'sort': sort,
        'total_count': paginator.count,
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category')
        .prefetch_related('variants', 'gallery_images'),
        slug=slug,
        is_active=True,
    )
    variants = list(product.variants.filter(is_active=True).order_by('display_order', 'price'))
    gallery = list(product.gallery_images.all().order_by('display_order'))
    related = (
        Product.objects.filter(category=product.category, is_active=True)
        .exclude(pk=product.pk)
        .select_related('category')
        .prefetch_related('variants')
        .annotate(min_price=Min('variants__price', filter=Q(variants__is_active=True)))
        .order_by('display_order', 'name')[:4]
    )
    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'variants': variants,
        'gallery': gallery,
        'related': related,
    })
