# -*- coding: utf-8 -*-
"""
Custom pagination classes module.
"""
from django.core.paginator import Paginator
from django.utils.functional import cached_property

from rest_framework.pagination import PageNumberPagination


class InstancePaginator(Paginator):
    """InstancePaginator is a custom paginator for the Instance model.

    It uses the approximate count stored in the XForm model num_of_submissions
    field instead of Django Paginator which does a count against the database.
    This is necessary to address slow performance for large datasets as well as
    working with a read replica.
    """

    @cached_property
    def count(self):
        try:
            return self.object_list.order_by().first().xform.num_of_submissions
        except (AttributeError, TypeError):
            pass

        return super(InstancePaginator, self).count


class StandardPageNumberPagination(PageNumberPagination):
    """
    StandardPageNumberPagination class - a custom PageNumberPagination class
    that sets default page size and page_size query parameter.
    """

    page_size = 1000
    page_size_query_param = "page_size"
    max_page_size = 10000


class InstancePageNumberPagination(StandardPageNumberPagination):
    """
    InstancePageNumberPagination class - a custom PageNumberPagination class
    that uses the InstancePaginator.
    """

    django_paginator_class = InstancePaginator
