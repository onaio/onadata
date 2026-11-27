# -*- coding: utf-8 -*-
"""
Pagination classes.
"""

from django.conf import settings
from django.core.paginator import Paginator
from django.core.signing import BadSignature, Signer
from django.db.models import F
from django.db.models.fields.tuple_lookups import Tuple, TupleGreaterThan, TupleLessThan
from django.utils.dateparse import parse_datetime
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from rest_framework.pagination import (
    InvalidPage,
    NotFound,
    PageNumberPagination,
    replace_query_param,
)
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
        if self.page.number == self.page.paginator.num_pages:
            return None

        url = self.request.build_absolute_uri()

        return replace_query_param(
            url, self.page_query_param, self.page.paginator.num_pages
        )

    def generate_link_header(self):
        """Generates pagination headers for a HTTP response object"""
        links = []

        for rel, link in (
            ("prev", self.get_previous_link()),
            ("next", self.get_next_link()),
            ("last", self.get_last_page_link()),
            ("first", self.get_first_page_link()),
        ):
            if link:
                links.append(f'<{link}>; rel="{rel}"')

        if not links:
            return {}

        return {"Link": ", ".join(links)}

    def get_paginated_response(self, data):
        """Override to remove the OrderedDict response and use headers"""
        return Response(data, headers=self.generate_link_header())


class CountFreePageNumberPagination(StandardPageNumberPagination):
    """Detect the next page by fetching one extra record instead of counting."""

    # pylint: disable=attribute-defined-outside-init
    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        self.page_size = self.get_page_size(request)
        try:
            self.page_number = int(request.query_params.get(self.page_query_param, 1))
        except (TypeError, ValueError) as exc:
            raise NotFound(self.invalid_page_message) from exc
        if self.page_number < 1:
            raise NotFound(self.invalid_page_message)

        offset = (self.page_number - 1) * self.page_size
        records = list(queryset[offset : offset + self.page_size + 1])
        if not records and self.page_number > 1:
            raise NotFound(self.invalid_page_message)
        self.has_next = len(records) > self.page_size
        return records[: self.page_size]

    def _page_link(self, number):
        url = replace_query_param(
            self.request.build_absolute_uri(), self.page_query_param, number
        )
        return replace_query_param(url, self.page_size_query_param, self.page_size)

    def get_next_link(self):
        return self._page_link(self.page_number + 1) if self.has_next else None

    def get_previous_link(self):
        return self._page_link(self.page_number - 1) if self.page_number > 1 else None

    def get_first_page_link(self):
        return self._page_link(1) if self.page_number > 1 else None

    def get_last_page_link(self):
        return None


class SubmissionCursorPagination(StandardPageNumberPagination):
    """Traverse submission IDs or timestamp and ID pairs with an indexed seek."""

    def __init__(self, form_id, ordering):
        self.form_id = form_id
        self.ordering = ordering
        self.descending = ordering.startswith("-")
        self.by_timestamp = ordering.lstrip("-") == "date_created"
        self.signer = Signer(salt="onadata.submission-pagination")
        self.next_url = None

    def _seek(self, queryset, token):
        try:
            form_id, ordering, pk, date = self.signer.unsign_object(token)
            if (form_id, ordering) != (self.form_id, self.ordering):
                raise ValueError
            if not isinstance(pk, int) or pk < 1:
                raise ValueError
            timestamp = parse_datetime(date) if self.by_timestamp else None
            if self.by_timestamp and (
                timestamp is None or timestamp.utcoffset() is None
            ):
                raise ValueError
        except (BadSignature, TypeError, ValueError, OverflowError) as exc:
            raise NotFound(_("Invalid submission cursor.")) from exc

        if timestamp is not None:
            lookup = TupleLessThan if self.descending else TupleGreaterThan
            return queryset.filter(
                lookup(Tuple(F("date_created"), F("id")), (timestamp, pk))
            )
        comparison = "id__lt" if self.descending else "id__gt"
        return queryset.filter(**{comparison: pk})

    def paginate_queryset(self, queryset, request, view=None):
        token = request.query_params.get("cursor")
        if token is not None:
            queryset = self._seek(queryset, token)
        page_size = self.get_page_size(request)
        order_id = "-id" if self.descending else "id"
        ordering = (self.ordering, order_id) if self.by_timestamp else (order_id,)
        records = list(queryset.order_by(*ordering)[: page_size + 1])
        page = records[:page_size]
        if len(records) > page_size:
            last = page[-1]
            boundary = last if isinstance(last, dict) else vars(last)
            date = boundary["date_created"].isoformat() if self.by_timestamp else None
            token = self.signer.sign_object(
                [self.form_id, self.ordering, boundary["id"], date]
            )
            url = replace_query_param(request.build_absolute_uri(), "cursor", token)
            self.next_url = replace_query_param(
                url, self.page_size_query_param, page_size
            )
        return page

    def generate_link_header(self):
        if self.next_url is None:
            return {}
        return {"Link": f'<{self.next_url}>; rel="next"'}


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

    # pylint: disable=attribute-defined-outside-init
    def paginate_queryset(self, queryset, request, view, count=None):
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

    def get_offset_limit(self, request, count: int) -> tuple[int, int]:
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
