from datetime import datetime
from typing import Optional
from django.http import JsonResponse, HttpResponseBase
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

from .connection import check_mongodb_connection, get_mongodb, mongodb_connection
from .models import UserProfile
from .serializers import UserProfileSerializer

logger = logging.getLogger(__name__)


@require_GET
def health_check(request):
    """Health check endpoint for MongoDB connection."""
    result = {
        "mongodb": {
            "enabled": False,
            "connected": False,
            "database": None,
            "collection_count": 0,
            "uptime_ms": 0,
        },
        "status": "error",
        "message": "MongoDB not enabled",
    }

    try:
        from django.conf import settings

        result["mongodb"]["enabled"] = getattr(settings, "MONGODB_ENABLED", False)

        if not check_mongodb_connection():
            if result["mongodb"]["enabled"]:
                result["message"] = "MongoDB is enabled but not connected"
                result["status"] = "warning"
            else:
                result["status"] = "ok"
                result["message"] = "MongoDB integration disabled"
            return JsonResponse(result, status=200 if result["status"] == "ok" else 200)

        # MongoDB is connected
        db = get_mongodb()
        result["mongodb"]["connected"] = True
        if db is not None:
            result["mongodb"]["database"] = db.name

        # Get collection count
        if db is not None:
            try:
                result["mongodb"]["collection_count"] = len(db.list_collection_names())
            except Exception as e:
                logger.warning(f"Could not get collection count: {e}")

        # Calculate uptime
        if mongodb_connection._client is not None:
            try:
                server_info = mongodb_connection._client.server_info()
                local_time = server_info.get("localTime", datetime.utcnow())
                result["mongodb"]["uptime_ms"] = (
                    datetime.utcnow() - local_time
                ).total_seconds() * 1000
            except Exception as e:
                logger.warning(f"Could not get server info: {e}")

        result["status"] = "ok"
        result["message"] = "MongoDB is connected and healthy"

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        result["message"] = str(e)
        result["status"] = "error"

    status_code = 200 if result["status"] == "ok" else 503
    return JsonResponse(result, status=status_code)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_profile_view(request) -> Response:
    """
    Handle user profile operations in MongoDB.
    
    GET: Retrieve user profile
    POST: Create or update user profile
    """
    if not check_mongodb_connection():
        return Response(
            {"error": "MongoDB connection not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    user_id = str(request.user.id)
    
    if request.method == 'GET':
        try:
            # Try to get existing profile
            profile = UserProfile.objects().get(user_id=user_id)
            if profile:
                serializer = UserProfileSerializer(profile)
                return Response(serializer.data)
            else:
                # Return empty profile data
                return Response({
                    "username": "",
                    "campaign": ""
                })
        except Exception as e:
            logger.error(f"Error retrieving user profile: {e}")
            return Response(
                {"error": "Failed to retrieve profile"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        try:
            # Check if profile already exists
            existing_profile = UserProfile.objects().get(user_id=user_id)
            
            # Add user_id to the data
            profile_data = request.data.copy()
            profile_data['user_id'] = user_id
            
            serializer = UserProfileSerializer(existing_profile, data=profile_data)
            if serializer.is_valid():
                profile = serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK if existing_profile else status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error saving user profile: {e}")
            return Response(
                {"error": "Failed to save profile"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Default return (should never reach here with the decorators)
    return Response(
        {"error": "Method not allowed"}, 
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request) -> Response:
    """
    Partially update user profile in MongoDB.
    """
    if not check_mongodb_connection():
        return Response(
            {"error": "MongoDB connection not available"}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    user_id = str(request.user.id)
    
    try:
        # Try to get existing profile
        existing_profile = UserProfile.objects().get(user_id=user_id)
        
        if not existing_profile:
            return Response(
                {"error": "Profile not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update only provided fields
        for key, value in request.data.items():
            if hasattr(existing_profile, key):
                setattr(existing_profile, key, value)
        
        existing_profile.updated_at = datetime.utcnow()
        existing_profile.save()
        
        serializer = UserProfileSerializer(existing_profile)
        return Response(serializer.data)
        
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        return Response(
            {"error": "Failed to update profile"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Default return (should never reach here with the decorators)
    return Response(
        {"error": "Method not allowed"}, 
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )
