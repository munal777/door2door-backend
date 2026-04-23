from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from django.db.models import Q

from .models import WeightSlab, ServiceTypePricing, LocationPricing
from .serializers import (
    WeightSlabSerializer,
    ServiceTypePricingSerializer,
    LocationPricingSerializer,
    LocationListSerializer,
    PriceEstimationSerializer,
)
from .services import PricingEstimationService, PricingEstimationError

from myproject.permissions import IsSystemAdmin
from myproject.utils import api_response


class WeightSlabListCreateAPIView(generics.ListCreateAPIView):
    """
    List all weight slabs or create a new weight slab
    """
    queryset = WeightSlab.objects.all()
    serializer_class = WeightSlabSerializer
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by package type
        package_type = self.request.query_params.get('package_type', None)
        if package_type:
            queryset = queryset.filter(package_type=package_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_201_CREATED
        )


class WeightSlabDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific weight slab
    GET: Retrieve weight slab details
    PUT/PATCH: Update weight slab
    DELETE: Delete weight slab
    """
    queryset = WeightSlab.objects.all()
    serializer_class = WeightSlabSerializer
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        
        return api_response(
            is_success=True,
            result= {
                "message": "Weight slab deleted successfully",
            },
            status_code=status.HTTP_204_NO_CONTENT
        )


class ServiceTypePricingListCreateAPIView(generics.ListCreateAPIView):
    """
    List all service type pricings or create a new one
    """
    queryset = ServiceTypePricing.objects.all()
    serializer_class = ServiceTypePricingSerializer
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by service type
        service_type = self.request.query_params.get('service_type', None)
        if service_type:
            queryset = queryset.filter(service_type=service_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_201_CREATED
        )


class ServiceTypePricingDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific service type pricing
    """
    queryset = ServiceTypePricing.objects.all()
    serializer_class = ServiceTypePricingSerializer
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        
        return api_response(
            is_success=True,
            result= {
                "message" : "Service type pricing deleted successfully",
            },
            status_code=status.HTTP_204_NO_CONTENT
        )

class LocationPricingListCreateAPIView(generics.ListCreateAPIView):
    """
    List all location pricings or create a new one
    """
    queryset = LocationPricing.objects.all()
    serializer_class = LocationPricingSerializer
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by city
        city = self.request.query_params.get('city', None)
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        # Filter by state
        state = self.request.query_params.get('state', None)
        if state:
            queryset = queryset.filter(state__icontains=state)
        
        # Filter by area type
        area_type = self.request.query_params.get('area_type', None)
        if area_type:
            queryset = queryset.filter(area_type=area_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Search by city or state
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(city__icontains=search) | Q(state__icontains=search)
            )
        
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_201_CREATED
        )


class LocationPricingDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific location pricing
    """
    queryset = LocationPricing.objects.all()
    serializer_class = LocationPricingSerializer
    permission_classes = [permissions.IsAuthenticated, IsSystemAdmin]
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        serializer.save()
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        
        return api_response(
            is_success=True,
            result= {
                "message": "Location pricing deleted successfully",
            },
            status_code=status.HTTP_204_NO_CONTENT
        )


class LocationListAPIView(generics.ListAPIView):
    """
    Public endpoint to list available locations for delivery
    """
    queryset = LocationPricing.objects.filter(is_active=True)
    serializer_class = LocationListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by state
        state = self.request.query_params.get('state', None)
        if state:
            queryset = queryset.filter(state__icontains=state)
        
        # Search by city or state
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(city__icontains=search) | Q(state__icontains=search)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        return api_response(
            result=serializer.data,
            is_success=True,
            status_code=status.HTTP_200_OK
        )


class PriceEstimationAPIView(APIView):
    """
    Calculate price estimation for a delivery using PricingEstimationService
    """

    def post(self, request, *args, **kwargs):
        serializer = PriceEstimationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return api_response(
                is_success=False,
                error_message=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Extract validated data
        data = serializer.validated_data
        
        try:
            # Use the pricing estimation service
            estimation = PricingEstimationService.estimate_price(
                package_type=data['package_type'],
                weight=data['weight'],
                quantity=data.get('quantity', 1),
                pickup_city=data['pickup_city'],
                pickup_state=data['pickup_state'],
                delivery_city=data['delivery_city'],
                delivery_state=data['delivery_state'],
                service_type=data['service_type'],
                length=data.get('length'),
                width=data.get('width'),
                height=data.get('height'),
            )
            
            return api_response(
                result=estimation,
                is_success=True,
                status_code=status.HTTP_200_OK
            )
            
        except PricingEstimationError as e:
            return api_response(
                is_success=False,
                error_message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return api_response(
                is_success=False,
                error_message=f"An error occurred while calculating price: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )