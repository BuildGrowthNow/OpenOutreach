# API Response Utilities
"""
This module provides utilities for consistent API responses across the application.
It standardizes the response format to include pagination, stats, and meta information
in a predictable structure.
"""

from typing import Any, Dict, Optional, List
from dataclasses import dataclass




@dataclass
class PaginationInfo:
    """Pagination metadata for list responses."""
    page: int
    limit: int
    total: int

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total + self.limit - 1) // self.limit if self.limit > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'page': self.page,
            'limit': self.limit,
            'total': self.total,
            'total_pages': self.total_pages,
        }


class APIResponseBuilder:
    """
    Builder class for consistent API responses.
    
    This class provides a standardized way to build API responses with:
    - data: The main response data (list or single object)
    - pagination: Pagination metadata (for list endpoints)
    - stats: Statistics/metrics (for analytics endpoints)
    - filters: Filter information (for filtered list endpoints)
    """
    
    def __init__(self):
        self._data: Optional[Any] = None
        self._pagination: Optional[PaginationInfo] = None
        self._stats: Optional[Dict[str, Any]] = None
        self._filters: Optional[Dict[str, Any]] = None
        self._meta: Optional[Dict[str, Any]] = None
        self._success: bool = True
        self._message: Optional[str] = None
    
    def set_data(self, data: Any) -> 'APIResponseBuilder':
        """Set the main response data."""
        self._data = data
        return self
    
    def set_pagination(self, page: int, limit: int, total: int) -> 'APIResponseBuilder':
        """Set pagination metadata."""
        self._pagination = PaginationInfo(
            page=page,
            limit=limit,
            total=total
        )
        return self
    
    def set_stats(self, stats: Dict[str, Any]) -> 'APIResponseBuilder':
        """Set statistics/metrics data."""
        self._stats = stats
        return self
    
    def set_filters(self, filters: Dict[str, Any]) -> 'APIResponseBuilder':
        """Set filter information."""
        self._filters = filters
        return self
    
    def set_meta(self, meta: Dict[str, Any]) -> 'APIResponseBuilder':
        """Set metadata (optional additional info)."""
        self._meta = meta
        return self
    
    def set_success(self, success: bool, message: Optional[str] = None) -> 'APIResponseBuilder':
        """Set success status and optional message."""
        self._success = success
        self._message = message
        return self
    
    def build(self) -> Dict[str, Any]:
        """Build the final response dictionary."""
        result: Dict[str, Any] = {'success': self._success}
        
        if self._message:
            result['message'] = self._message
        
        if self._data is not None:
            result['data'] = self._data
        
        if self._pagination is not None:
            result['pagination'] = self._pagination.to_dict()
        
        if self._stats is not None:
            result['stats'] = self._stats
        
        if self._filters is not None:
            result['filters'] = self._filters
        
        if self._meta is not None:
            result['meta'] = self._meta
        
        return result


def create_pagination_response(
    data: Any,
    page: int,
    limit: int,
    total: int,
    filters: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized pagination response.
    
    Args:
        data: The list or item to return
        page: Current page number
        limit: Number of items per page
        total: Total number of items
        filters: Optional filter information
        meta: Optional metadata
        
    Returns:
        Dictionary with standardized response format
    """
    pagination = PaginationInfo(page=page, limit=limit, total=total)
    
    response: Dict[str, Any] = {
        'data': data,
        'pagination': pagination.to_dict(),
    }
    
    if filters:
        response['filters'] = filters
    
    if meta:
        response['meta'] = meta
    
    return response


def create_stats_response(
    stats: Dict[str, Any],
    period: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized stats/analytics response.
    
    Args:
        stats: The statistics/metrics data
        period: Optional time period (e.g., '7d', '30d')
        meta: Optional metadata
        
    Returns:
        Dictionary with standardized response format
    """
    response: Dict[str, Any] = {
        'data': stats,
        'stats': stats,  # For backward compatibility
    }
    
    if period:
        response['period'] = period
    
    if meta:
        response['meta'] = meta
    
    return response


def create_message_response(
    success: bool,
    message: str,
    data: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Create a simple message response (for non-data endpoints).
    
    Args:
        success: Whether the operation succeeded
        message: Human-readable message
        data: Optional additional data
        
    Returns:
        Dictionary with standardized response format
    """
    response: Dict[str, Any] = {
        'success': success,
        'message': message,
    }
    
    if data is not None:
        response['data'] = data
    
    return response


def create_list_response(
    items: List[Any],
    page: int,
    limit: int,
    total: int,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized list response with pagination.
    
    This is a convenience wrapper around create_pagination_response.
    
    Args:
        items: List of items to return
        page: Current page number
        limit: Number of items per page
        total: Total number of items
        filters: Optional filter information
        
    Returns:
        Dictionary with standardized response format
    """
    return create_pagination_response(
        data=items,
        page=page,
        limit=limit,
        total=total,
        filters=filters,
    )


def create_single_response(
    item: Any,
    success: bool = True,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized single-item response.
    
    Args:
        item: The single item to return
        success: Whether the operation succeeded
        message: Optional success message
        
    Returns:
        Dictionary with standardized response format
    """
    response: Dict[str, Any] = {
        'data': item,
    }
    
    if message:
        response['message'] = message
    
    if not success:
        response['success'] = False
    
    return response