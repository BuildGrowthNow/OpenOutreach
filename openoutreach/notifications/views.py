from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils import timezone

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    """
    API view for listing and managing notifications.

    GET /api/notifications/ - List user's notifications (latest first, with pagination)
    POST /api/notifications/read-all/ - Mark all as read
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List user's notifications with optional filters."""
        notifications = Notification.objects.filter(recipient=request.user).order_by(
            "-created_at"
        )

        # Optional filters
        is_read = request.query_params.get("is_read")
        if is_read is not None:
            notifications = notifications.filter(is_read=is_read.lower() == "true")

        notification_type = request.query_params.get("type")
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)

        # Pagination
        page = request.query_params.get("page")
        limit = request.query_params.get("limit")

        total = notifications.count()
        if page and limit:
            try:
                page_num = int(page)
                limit_num = int(limit)
                start = (page_num - 1) * limit_num
                end = start + limit_num
                notifications = notifications[start:end]
            except (ValueError, TypeError):
                pass

        serializer = NotificationSerializer(notifications, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {
                    "page": int(page) if page else 1,
                    "limit": int(limit) if limit else len(serializer.data),
                    "total": total,
                },
                "unread_count": Notification.objects.filter(
                    recipient=request.user, is_read=False
                ).count(),
            }
        )

    def post(self, request):
        """Mark all notifications as read."""
        Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return Response(
            {"success": True, "message": "All notifications marked as read"}
        )


class NotificationMarkAllAsReadView(APIView):
    """
    API view to mark all notifications as read.

    POST /api/notifications/read-all/ - Mark all notifications as read
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Mark all notifications as read."""
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({"success": True, "updated_count": updated})


class NotificationSummaryView(APIView):
    """
    API view to get notification summary (unread count + recent notifications).

    GET /api/notifications/summary/ - Get notification summary
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get notification summary."""
        unread_count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        recent_notifications = Notification.objects.filter(
            recipient=request.user
        ).order_by("-created_at")[:10]

        from .serializers import NotificationSerializer

        return Response(
            {
                "unread_count": unread_count,
                "recent_notifications": NotificationSerializer(
                    recent_notifications, many=True
                ).data,
            }
        )


class NotificationDetailView(APIView):
    """
    API view for individual notification operations.

    GET /api/notifications/{id}/ - Get specific notification
    PATCH /api/notifications/{id}/read/ - Mark as read
    DELETE /api/notifications/{id}/ - Delete notification
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        """Get notification for user or return None."""
        try:
            return Notification.objects.get(pk=pk, recipient=user)
        except Notification.DoesNotExist:
            return None

    def get(self, request, pk):
        """Get a specific notification."""
        notification = self.get_object(pk, request.user)
        if not notification:
            return Response(
                {"error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = NotificationSerializer(notification)
        return Response(serializer.data)

    def patch(self, request, pk):
        """Mark notification as read."""
        notification = self.get_object(pk, request.user)
        if not notification:
            return Response(
                {"error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.mark_as_read()
        return Response({"success": True, "message": "Notification marked as read"})

    def delete(self, request, pk):
        """Delete a notification."""
        notification = self.get_object(pk, request.user)
        if not notification:
            return Response(
                {"error": "Notification not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.delete()
        return Response({"success": True, "message": "Notification deleted"})
