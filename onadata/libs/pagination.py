# -*- coding: utf-8 -*-
"""
Pagination classes.
"""
from typing import Tuple
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.utils.functional import cached_property

from rest_framework.pagination import (
    InvalidPage,
    NotFound,
    PageNumberPagination,
    replace_query_param,
)
from rest_framework.request import Request
from rest_framework.response import Response


class StandardPageNumberPagination(PageNumberPagination):
    """The Standard PageNumberPagination class

    Set's the default ``page_size`` to 1000 with a maximum page_size of 10,000 records
    per page.
    """

    page_size = 1000
    page_size_query_param = "page_size"
    max_page_size = getattr(settings, "STANDARD_PAGINATION_MAX_PAGE_SIZE", 10000)

    def get_first_page_link(self):
        """Returns the URL to the first page."""
        if self.page.number == 1:
            return None

        url = self.request.build_absolute_uri()

        return replace_query_param(url, self.page_query_param, 1)

    def get_last_page_link(self):
        """Returns the URL to the last page."""
        if self.page.number == self.paginator.num_pages:
            return None

        url = self.request.build_absolute_uri()

        return replace_query_param(url, self.page_query_param, self.paginator.num_pages)

    def generate_link_header(self, request: Request, queryset: QuerySet):
        """Generates pagination headers for a HTTP response object"""
        links = []
        page_size = self.get_page_size(request)
        if not page_size:
            return {}
        page_number = request.query_params.get(self.page_query_param, 1)
        # pylint: disable=attribute-defined-outside-init
        self.paginator = self.django_paginator_class(queryset, page_size)
        self.request = request

        try:
            self.page = self.paginator.page(page_number)
        except InvalidPage:
            return {}

        for rel, link in (
            ("prev", self.get_previous_link()),
            ("next", self.get_next_link()),
            ("last", self.get_last_page_link()),
            ("first", self.get_first_page_link()),
        ):
            if link:
                links.append(f'<{link}>; rel="{rel}"')

        return {"Link": ", ".join(links)}

    def get_paginated_response(self, data):
        """Override to remove the OrderedDict response"""
        return Response(data)


class CountOverridablePaginator(Paginator):
    """Count override Paginator

    Allows overriding the count especially in the event it may be expensive request.
    """

    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        object_list,
        per_page,
        orphans: int = 0,
        allow_empty_first_page: bool = True,
        count_override: int = None,
    ) -> None:
        self.count_override = count_override
        super().__init__(
            object_list,
            per_page,
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page,
        )

    @cached_property
    def count(self):
        if self.count_override:
            return self.count_override
        return super().count


class CountOverridablePageNumberPagination(StandardPageNumberPagination):
    """Count override PageNumberPagination

    Allows overriding the count especially in the event it may be expensive request.
    """

    django_paginator_class = CountOverridablePaginator

    def paginate_queryset(self, queryset, request, view, count=None):
        # pylint: disable=attribute-defined-outside-init
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        paginator = self.django_paginator_class(
            queryset, page_size, count_override=count
        )
        page_number = request.query_params.get(self.page_query_param, 1)
        if page_number in self.last_page_strings:
            page_number = paginator.num_pages

        try:
            self.page = paginator.page(page_number)
        except InvalidPage as exc:
            msg = self.invalid_page_message.format(
                page_number=page_number, message=str(exc)
            )
            raise NotFound(msg) from exc

        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True

        self.request = request
        return list(self.page)


class RawSQLQueryPaginator(CountOverridablePaginator):
    """Paginator class for raw SQL queries"""

    def page(self, number):
        """Return page

        self.object_list is NOT sliced because self.object_list should
        have been paginated via OFFSET and LIMIT before creating a
        RawPaginator instance
        """
        number = self.validate_number(number)
        return self._get_page(self.object_list, number, self)


class RawSQLQueryPageNumberPagination(CountOverridablePageNumberPagination):
    """PageNumberPagination class for raw SQL queries"""

    django_paginator_class = RawSQLQueryPaginator

    def get_offset_limit(self, request, count: int) -> Tuple[int, int]:
        """Returns the offset and limit to be used in a raw SQL query"""
        page_size = self.get_page_size(request)
        # pass an empty object_list since we are not handling any pagination
        # at this point, we are specifically interested in the count
        paginator = self.django_paginator_class([], page_size, count_override=count)
        page_number = paginator.validate_number(
            self.get_page_number(request, paginator)
        )
        offset = (page_number - 1) * paginator.per_page
        limit = paginator.per_page

        return (offset, limit)
