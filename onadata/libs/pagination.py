import math
from typing import Union
from urllib.parse import urlparse, parse_qs

from django.core.paginator import Paginator
from django.conf import settings
from rest_framework.pagination import (
    PageNumberPagination, InvalidPage, NotFound)
from rest_framework.request import Request


class StandardPageNumberPagination(PageNumberPagination):
    page_size = 1000
    page_size_query_param = 'page_size'
    max_page_size = getattr(
        settings, "STANDARD_PAGINATION_MAX_PAGE_SIZE", 10000)


class CountOverridablePaginator(Paginator):
    def __init__(
            self, object_list, per_page,
            orphans: int = 0, allow_empty_first_page: bool = True,
            count_override: int = None) -> None:
        self.count_override = count_override
        super().__init__(
            object_list, per_page,
            orphans=orphans, allow_empty_first_page=allow_empty_first_page)

    @property
    def count(self):
        if self.count_override:
            return self.count_override
        return super().count


class CountOverridablePageNumberPagination(StandardPageNumberPagination):
    django_paginator_class = CountOverridablePaginator

    def paginate_queryset(self, queryset, request, view, count=None):
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        paginator = self.django_paginator_class(
            queryset,
            page_size,
            count_override=count
        )
        page_number = request.query_params.get(self.page_query_param, 1)
        if page_number in self.last_page_strings:
            page_number = paginator.num_pages

        try:
            self.page = paginator.page(page_number)
        except InvalidPage as exc:
            msg = self.invalid_page_message.format(page_number=page_number,
                                                   message=str(exc))
            raise NotFound(msg)

        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True

        self.request = request
        return list(self.page)


def generate_pagination_headers(
    request: Request, no_of_records: int, current_page_size: Union[int, str],
    current_page: Union[int, str]
) -> dict:
    url = urlparse(request.build_absolute_uri())
    base_url = f"{url.scheme}://{url.netloc}{url.path}?"
    if url.query:
        query_params = parse_qs(url.query)
        query_string = None
        for param_key, param_values in query_params.items():
            if param_key not in ['page_size', 'page']:
                param_value = ','.join(param_values)
                query = f'{param_key}={param_value}&'
                if not query_string:
                    query_string = query
                else:
                    query_string += query

        base_url += f'{query_string}'

    next_page_url = None
    prev_page_url = None
    first_page_url = None
    last_page_url = None
    links = []

    if isinstance(current_page, str):
        try:
            current_page = int(current_page)
        except ValueError:
            return

    if isinstance(current_page_size, str):
        try:
            current_page_size = int(current_page_size)
        except ValueError:
            return

    if (current_page * current_page_size) < no_of_records:
        next_page_url = (
            f"{base_url}page={current_page + 1}&"
            f"page_size={current_page_size}")

    if current_page > 1:
        prev_page_url = (
            f"{base_url}page={current_page - 1}"
            f"&page_size={current_page_size}")

    last_page = math.ceil(no_of_records / current_page_size)
    if last_page != current_page and last_page != current_page + 1:
        last_page_url = (
            f"{base_url}page={last_page}&page_size={current_page_size}"
        )

    if current_page != 1:
        first_page_url = (
            f"{base_url}page=1&page_size={current_page_size}"
        )

    for rel, link in (
            ('prev', prev_page_url),
            ('next', next_page_url),
            ('last', last_page_url),
            ('first', first_page_url)):
        if link:
            links.append(f'<{link}>; rel="{rel}"')

    return {'Link': ', '.join(links)}
