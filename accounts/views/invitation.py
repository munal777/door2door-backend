from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404

from myproject.utils import api_response
from accounts.models.invitation import ProviderInvitation
from accounts.serializers.invitation import (
    SendInvitationSerializer,
    InvitationDetailSerializer,
    InvitationListSerializer,
    InvitationTokenValidationSerializer,
)
from accounts.tasks import send_invitation_email
from myproject.permissions import HasInvitationManagementPermission


class InvitationTokenValidationView(generics.GenericAPIView):
    """
    Public endpoint to validate invitation token before registration.

    POST /api/accounts/invitations/validate/
    {
        "invitation_token": "...",
        "registration_type": "staff" | "rider" (optional)
    }
    """

    serializer_class = InvitationTokenValidationSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                error_message=serializer.errors,
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        invitation_token = serializer.validated_data["invitation_token"]
        registration_type = serializer.validated_data.get("registration_type")

        try:
            invitation = ProviderInvitation.objects.select_related("courier_provider").get(
                invitation_token=invitation_token
            )
        except ProviderInvitation.DoesNotExist:
            return api_response(
                error_message="Invalid invitation token. Please check your invitation link.",
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not invitation.is_valid():
            if invitation.status == ProviderInvitation.InvitationStatus.ACCEPTED:
                message = "This invitation has already been used."
            elif invitation.status == ProviderInvitation.InvitationStatus.REVOKED:
                message = "This invitation has been revoked. Please contact the courier company."
            else:
                message = "This invitation has expired. Please request a new invitation."

            return api_response(
                error_message=message,
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if registration_type == "staff" and invitation.role not in [
            ProviderInvitation.InvitationRole.ADMIN,
            ProviderInvitation.InvitationRole.OPERATIONS,
        ]:
            return api_response(
                error_message="This invitation is not valid for staff registration.",
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if registration_type == "rider" and invitation.role != ProviderInvitation.InvitationRole.RIDER:
            return api_response(
                error_message="This invitation is not valid for rider registration.",
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not invitation.courier_provider.is_active:
            return api_response(
                error_message="The courier company is currently inactive. Please contact support.",
                is_success=False,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_response(
            result={
                "email": invitation.email,
                "role": invitation.role,
                "courier_name": invitation.courier_provider.name,
                "courier_city": invitation.courier_provider.city,
                "courier_state": invitation.courier_provider.state,
                "expires_at": invitation.expires_at,
                "is_valid": True,
            },
            is_success=True,
            status_code=status.HTTP_200_OK,
        )


class SendInvitationView(generics.CreateAPIView):
    """
    API endpoint for provider admin to send invitation to rider or staff.
    Only courier provider admins can send invitations.
    """
    serializer_class = SendInvitationSerializer
    permission_classes = [IsAuthenticated, HasInvitationManagementPermission]

    def create(self, request, *args, **kwargs):
        """Send invitation"""
        # Get courier provider from request (already attached by authentication)
        courier_provider = request.courier
        
        if not courier_provider:
            return api_response(
                error_message='You are not authorized to send invitations. Only courier provider admins can send invitations.',
                is_success=False,
                status_code=status.HTTP_403_FORBIDDEN
            )

        # Add context to serializer
        serializer = self.get_serializer(
            data=request.data,
            context={
                'courier_provider': courier_provider,
                'invited_by': request.user
            }
        )

        if serializer.is_valid():
            try:
                invitation = serializer.save()
                
                # Send invitation email
                email_sent = send_invitation_email.delay(invitation.id)
                
                if not email_sent:
                    # If email fails, delete the invitation
                    invitation.delete()
                    return api_response(
                        error_message='Failed to send invitation email. Please try again.',
                        is_success=False,
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                
                return api_response(
                    result={
                        'message': f'Invitation sent successfully to {invitation.email}'
                    },
                    is_success=True,
                    status_code=status.HTTP_201_CREATED
                )
            except Exception as e:
                return api_response(
                    error_message=f'Failed to send invitation: {str(e)}',
                    is_success=False,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class InvitationListView(generics.ListAPIView):
    """
    API endpoint to list all invitations sent by a courier provider.
    Accessible by staff with invitation management permissions.
    """
    serializer_class = InvitationListSerializer
    permission_classes = [IsAuthenticated, HasInvitationManagementPermission]

    def get_queryset(self):
        """Get invitations for the provider"""
        courier_provider = self.request.courier
        
        if not courier_provider:
            return ProviderInvitation.objects.none()

        queryset = ProviderInvitation.objects.filter(
            courier_provider=courier_provider
        ).select_related('invited_by')

        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def list(self, request, *args, **kwargs):
        """List invitations"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return api_response(
            result={
                'count': queryset.count(),
                'invitations': serializer.data
            },
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class InvitationDetailView(generics.RetrieveAPIView):
    """
    API endpoint to get details of a specific invitation.
    Accessible by staff with invitation management permissions.
    
    GET /api/accounts/invitations/<id>/
    """
    serializer_class = InvitationDetailSerializer
    permission_classes = [IsAuthenticated, HasInvitationManagementPermission]

    def get_queryset(self):
        """Get invitations for the provider"""
        courier_provider = self.request.courier
        
        if not courier_provider:
            return ProviderInvitation.objects.none()

        return ProviderInvitation.objects.filter(
            courier_provider=courier_provider
        ).select_related('invited_by', 'courier_provider')

    def retrieve(self, request, *args, **kwargs):
        """Get invitation details"""
        invitation = self.get_object()
        serializer = self.get_serializer(invitation)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, HasInvitationManagementPermission])
def revoke_invitation(request, invitation_id):
    """
    Revoke a pending invitation.
    Only provider admins can revoke invitations.
    
    POST /api/accounts/invitations/<id>/revoke/
    """
    courier_provider = request.courier
    
    if not courier_provider:
        return api_response(
            error_message='You are not authorized to revoke invitations.',
            is_success=False,
            status_code=status.HTTP_403_FORBIDDEN
        )

    invitation = get_object_or_404(
        ProviderInvitation,
        id=invitation_id,
        courier_provider=courier_provider
    )

    if invitation.revoke():
        return api_response(
            result={
                'message': f'Invitation to {invitation.email} has been revoked.',
                'invitation_id': invitation.id
            },
            is_success=True,
            status_code=status.HTTP_200_OK
        )
    else:
        return api_response(
            error_message='Cannot revoke invitation. It may have already been accepted, expired, or revoked.',
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST
        )