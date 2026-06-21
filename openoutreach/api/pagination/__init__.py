# API Pagination Package

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status
from collections import OrderedDict


class StandardPagination(PageNumberPagination):
    """
    Standard pagination class with customizable page size and max page size.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class SmallPagination(PageNumberPagination):
    """
    Pagination class with smaller page size for detailed views.
    """
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 20
    
    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class LargePagination(PageNumberPagination):
    """
    Pagination class with larger page size for bulk operations.
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000
    
    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class CursorPagination(PageNumberPagination):
    """
    Cursor-based pagination for sorted views.
    """
    page_size = 20
    cursor_query_param = 'cursor'
    ordering = '-created_at'


class StandardAPIResponse:
    """
    Standardized API response format.
    """
    
    @staticmethod
    def success(data=None, message="Success", status_code=status.HTTP_200_OK):
        """
        Create a success response.
        """
        response = {
            'success': True,
            'message': message
        }
        if data is not None:
            response['data'] = data
        return Response(response, status=status_code)
    
    @staticmethod
    def error(message="An error occurred", errors=None, status_code=status.HTTP_400_BAD_REQUEST):
        """
        Create an error response.
        """
        response = {
            'success': False,
            'message': message
        }
        if errors is not None:
            response['errors'] = errors
        return Response(response, status=status_code)
    
    @staticmethod
    def pagination_response(data, pagination_info):
        """
        Create a pagination response.
        """
        return Response({
            'success': True,
            'data': data,
            'pagination': pagination_info
        })