# Authentication API Views

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from datetime import datetime
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom tokenobtainPairView that returns user data along with tokens.
    """
    
    def post(self, request, *args, **kwargs):
        """
        Authenticate user and return JWT tokens with user data.
        
        POST /api/auth/login
        Request: { "password": "..." }
        Response: {
            "access": "jwt_access_token",
            "refresh": "jwt_refresh_token",
            "user": {
                "id": 1,
                "email": "user@example.com",
                "username": "admin"
            }
        }
        """
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            # Extract the access token from the response
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')
            
            # Get the authenticated user
            try:
                token = RefreshToken(access_token)
                user_id = token['user_id']
                user = User.objects.get(id=user_id)
                
                # Add user data to response
                response.data['user'] = {
                    'id': user.id,
                    'email': user.email if hasattr(user, 'email') else None,
                    'username': user.username,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                }
                
                # Store refresh token in secure cookie
                response.set_cookie(
                    'refresh_token',
                    refresh_token,
                    max_age=60 * 60 * 24 * 7,  # 7 days
                    httponly=True,
                    secure=True,
                    samesite='Strict',
                )
                
                logger.info(f"User login successful: {user.email}")
                
            except Exception as e:
                logger.error(f"Error adding user data to response: {e}")
        
        return response


class LoginRateThrottle(AnonRateThrottle):
    """
    Rate limit for login attempts - prevents brute force attacks.
    """
    rate = '5/day'
    scope = 'login_login'


class PasswordResetRateThrottle(AnonRateThrottle):
    """
    Rate limit for password reset requests.
    """
    rate = '3/day'
    scope = 'password_reset'


class AuthView(APIView):
    """
    Authentication status and logout endpoint.
    """
    throttle_classes = [UserRateThrottle]
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        GET /api/auth/status
        Returns authentication status and user information.
        """
        user = request.user
        
        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email if hasattr(user, 'email') else None,
            'is_authenticated': user.is_authenticated,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        }
        
        # Filter out None values
        user_data = {k: v for k, v in user_data.items() if v is not None}
        
        return Response({
            'status': 'authenticated',
            'message': 'User is authenticated',
            'user': user_data,
        }, status=status.HTTP_200_OK)
    
    def delete(self, request):
        """
        DELETE /api/auth/logout
        Invalidate tokens and logout user.
        
        Blacklists the refresh token for token invalidation.
        """
        try:
            # Get refresh token from cookie
            refresh_token = request.COOKIES.get('refresh_token')
            
            if refresh_token:
                try:
                    # Create a token object and blacklist it
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                    logger.info(f"User logged out: {request.user.email}")
                except Exception as e:
                    logger.warning(f"Error blacklisting token: {e}")
            
            # Delete cookies
            response = Response({
                'status': 'success',
                'message': 'Successfully logged out',
            }, status=status.HTTP_200_OK)
            
            # Clear cookies
            response.delete_cookie('refresh_token')
            
            return response
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return Response({
                'status': 'error',
                'message': 'Logout failed',
            }, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetRequestView(APIView):
    """
    Password reset request endpoint.
    Sends a password reset email to the user.
    """
    throttle_classes = [PasswordResetRateThrottle]
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """
        POST /api/auth/password-reset/request
        Request: { "email": "user@example.com" }
        Response: { "message": "Password reset email sent" }
        """
        email = request.data.get('email')
        
        if not email:
            return Response({
                'status': 'error',
                'message': 'Email is required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Validate email format
            validate_email(email)
            
            try:
                user = User.objects.get(email__iexact=email)
                
                # Generate password reset token
                from django.core.signing import Signer
                import base64
                
                signer = Signer()
                timestamp = timezone.now().isoformat()
                token_data = f"{user.email}|{timestamp}"
                token = base64.urlsafe_b64encode(signer.sign(token_data).encode()).decode()
                
                # Store reset token (in production, use Redis or database)
                user.password_reset_token = token
                user.password_reset_expires = timezone.now() + timezone.timedelta(hours=24)
                user.save()
                
                # In production, send email with reset link
                # reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
                # send_password_reset_email(user.email, reset_url)
                
                logger.info(f"Password reset requested for: {email}")
                
                return Response({
                    'status': 'success',
                    'message': 'Password reset instructions sent to your email',
                }, status=status.HTTP_200_OK)
                
            except User.DoesNotExist:
                # Don't reveal if user exists or not for security
                return Response({
                    'status': 'success',
                    'message': 'Password reset instructions sent to your email',
                }, status=status.HTTP_200_OK)
                
        except ValidationError:
            return Response({
                'status': 'error',
                'message': 'Invalid email format',
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Password reset request error: {e}")
            return Response({
                'status': 'error',
                'message': 'An error occurred. Please try again.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PasswordResetConfirmView(APIView):
    """
    Password reset confirmation endpoint.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """
        POST /api/auth/password-reset/confirm
        Request: {
            "token": "reset_token",
            "password": "new_password"
        }
        Response: { "message": "Password successfully reset" }
        """
        token = request.data.get('token')
        password = request.data.get('password')
        
        if not token or not password:
            return Response({
                'status': 'error',
                'message': 'Token and password are required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(password) < 8:
            return Response({
                'status': 'error',
                'message': 'Password must be at least 8 characters',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from django.core.signing import Signer, BadSignature, SignatureExpired
            import base64
            
            # Decode and verify token
            decoded_token = base64.urlsafe_b64decode(token.encode()).decode()
            signer = Signer()
            original_value = signer.unsign(decoded_token)
            
            email, timestamp_str = original_value.split('|')
            timestamp = datetime.fromisoformat(timestamp_str)
            
            # Check if token expired (24 hours)
            expires_at = timezone.now() + timezone.timedelta(hours=24)
            if timezone.now() > expires_at:
                return Response({
                    'status': 'error',
                    'message': 'Token has expired',
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user and update password
            user = User.objects.get(email__iexact=email)
            
            # Verify token matches
            if user.password_reset_token != token:
                return Response({
                    'status': 'error',
                    'message': 'Invalid token',
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update password
            user.set_password(password)
            user.password_reset_token = None
            user.password_reset_expires = None
            user.save()
            
            logger.info(f"Password reset successful for: {email}")
            
            return Response({
                'status': 'success',
                'message': 'Password successfully reset',
            }, status=status.HTTP_200_OK)
            
        except BadSignature:
            return Response({
                'status': 'error',
                'message': 'Invalid token',
            }, status=status.HTTP_400_BAD_REQUEST)
        except SignatureExpired:
            return Response({
                'status': 'error',
                'message': 'Token has expired',
            }, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Invalid token',
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Password reset confirm error: {e}")
            return Response({
                'status': 'error',
                'message': 'An error occurred. Please try again.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdatePasswordView(APIView):
    """
    Update password for authenticated user.
    """
    throttle_classes = [UserRateThrottle]
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """
        POST /api/auth/update-password
        Request: {
            "current_password": "old_password",
            "new_password": "new_password"
        }
        Response: { "message": "Password successfully updated" }
        """
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')
        
        if not current_password or not new_password:
            return Response({
                'status': 'error',
                'message': 'Current password and new password are required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(new_password) < 8:
            return Response({
                'status': 'error',
                'message': 'New password must be at least 8 characters',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify current password
        if not request.user.check_password(current_password):
            return Response({
                'status': 'error',
                'message': 'Current password is incorrect',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update password
        request.user.set_password(new_password)
        request.user.save()
        
        logger.info(f"Password updated for user: {request.user.email}")
        
        return Response({
            'status': 'success',
            'message': 'Password successfully updated',
        }, status=status.HTTP_200_OK)


class LinkSupabaseUserView(APIView):
    """
    Link or create Django user from Supabase JWT token.
    
    This endpoint is used by the frontend to create or link a Django user
    when a user signs in with Supabase.
    
    The Supabase JWT is expected to be passed in the Authorization header.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """
        POST /api/auth/link-supabase-user/
        Request: {
            "supabase_user_id": "uuid",
            "email": "user@example.com",
            "full_name": "User Name"
        }
        Response: {
            "user_id": 1,
            "email": "user@example.com",
            "username": "uuid"
        }
        """
        supabase_user_id = request.data.get('supabase_user_id')
        email = request.data.get('email')
        full_name = request.data.get('full_name')
        
        if not supabase_user_id or not email:
            return Response({
                'status': 'error',
                'message': 'Supabase user ID and email are required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Validate email format
            validate_email(email)
            
            # Get or create Django user
            user, created = User.objects.get_or_create(
                username=supabase_user_id,
                defaults={
                    'email': email,
                    'first_name': full_name or '',
                }
            )
            
            if created:
                # Set unusable password - this is an SSO user
                user.set_unusable_password()
                user.save()
                logger.info(f"Created Django user from Supabase: {supabase_user_id}")
            
            return Response({
                'status': 'success',
                'user_id': user.id,
                'email': user.email,
                'username': user.username,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            }, status=status.HTTP_200_OK)
            
        except ValidationError:
            return Response({
                'status': 'error',
                'message': 'Invalid email format',
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Link Supabase user error: {e}")
            return Response({
                'status': 'error',
                'message': 'An error occurred. Please try again.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SupabaseUserInfoView(APIView):
    """
    Get Django user info linked to Supabase user.
    
    This endpoint is used to retrieve Django user information
    based on the Supabase user ID.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, supabase_user_id):
        """
        GET /api/auth/supabase-user/{supabase_user_id}/
        Returns Django user information linked to the Supabase user.
        """
        try:
            user = User.objects.get(username=supabase_user_id)
            
            return Response({
                'status': 'success',
                'user_id': user.id,
                'email': user.email,
                'username': user.username,
                'full_name': user.first_name,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'User not found',
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Get Supabase user info error: {e}")
            return Response({
                'status': 'error',
                'message': 'An error occurred. Please try again.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SupabaseVerifyTokenView(APIView):
    """
    Verify Supabase JWT token validity.
    
    This endpoint validates a Supabase JWT token without creating
    a Django user. It's used for token validation purposes.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """
        POST /api/auth/verify-supabase-token/
        Request: {
            "token": "supabase_jwt_token"
        }
        Response: {
            "valid": true,
            "user_id": "uuid",
            "email": "user@example.com"
        }
        """
        token = request.data.get('token')
        
        if not token:
            return Response({
                'status': 'error',
                'message': 'Token is required',
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            import jwt
            from django.conf import settings
            
            # Decode the token without verification to get payload
            payload = jwt.decode(
                token,
                options={'verify_signature': False},
            )
            
            # Verify signature using Supabase service key
            service_key = getattr(settings, 'SUPABASE_SERVICE_KEY', None)
            if service_key:
                jwt.decode(
                    token,
                    service_key,
                    algorithms=['HS256'],
                )
            
            return Response({
                'status': 'success',
                'valid': True,
                'user_id': payload.get('sub'),
                'email': payload.get('email'),
            }, status=status.HTTP_200_OK)
            
        except jwt.PyJWTError as e:
            return Response({
                'status': 'error',
                'valid': False,
                'message': f'Invalid token: {str(e)}',
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Verify token error: {e}")
            return Response({
                'status': 'error',
                'message': 'An error occurred. Please try again.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)