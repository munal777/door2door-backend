from rest_framework import generics, status

from myproject.permissions import IsConsumer
from myproject.utils import api_response

from accounts.models import Address
from accounts.serializers.consumer import AddressSerializer
from accounts.serializers.profile import ConsumerProfileSerializer


class ConsumerProfileUpdateView(generics.UpdateAPIView):
    """Update consumer profile details."""
    permission_classes = [IsConsumer]
    serializer_class = ConsumerProfileSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            return api_response(
                result=serializer.data,
                is_success=True,
                status_code=status.HTTP_200_OK,
            )
        
        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class AddressListCreateView(generics.ListCreateAPIView):
    """List and create saved addresses for authenticated consumers."""

    permission_classes = [IsConsumer]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return AddressSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            address = serializer.save()
            output = AddressSerializer(address).data
            return api_response(
                result=output,
                is_success=True,
                status_code=status.HTTP_201_CREATED,
            )

        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete a single saved address for consumers."""

    permission_classes = [IsConsumer]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return AddressSerializer

    def retrieve(self, request, *args, **kwargs):
        address = self.get_object()
        serializer = self.get_serializer(address)
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        address = self.get_object()
        serializer = AddressSerializer(address, data=request.data, partial=partial, context=self.get_serializer_context())

        if serializer.is_valid():
            updated_address = serializer.save()
            output = AddressSerializer(updated_address).data
            return api_response(
                result=output,
                is_success=True,
                status_code=status.HTTP_200_OK,
            )

        return api_response(
            error_message=serializer.errors,
            is_success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        address = self.get_object()
        address.delete()
        return api_response(
            result={'message': 'Address deleted successfully.'},
            is_success=True,
            status_code=status.HTTP_200_OK,
        )
