from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
class CustomPageNumberPagination(PageNumberPagination):
    """
    Custom pagination class using page number pagination.

    No arguments are required to use this pagination class. It sets a default
    page size of 20 items per page and adds custom metadata to the response.

    Usage:
        Simply include this pagination class in your DRF settings or apply it to a view.

    """
    page_size = 20  # Or use `page_size_query_param = 'page_size'` to make it dynamic

    def get_paginated_response(self, data):
        """
        Returns a customized paginated response structure.

        Args:
            data (list): The serialized data for the current page.

        Returns:
            Response: A Response object containing pagination metadata and results.
        """
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
