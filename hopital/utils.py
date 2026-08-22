from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def paginate_queryset(request, queryset, per_page=6, page_param='page'):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(page_param, 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    extra_query = get_query_string(request, exclude=[page_param])
    return page_obj, extra_query


def get_query_string(request, exclude=None):
    params = request.GET.copy()
    exclude = exclude or []
    for key in exclude:
        params.pop(key, None)
    return params.urlencode()


