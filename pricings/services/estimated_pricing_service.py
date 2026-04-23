from decimal import Decimal
from typing import Dict, Optional

from ..models import WeightSlab, ServiceTypePricing, LocationPricing


class PricingEstimationError(Exception):
    """Custom exception for pricing estimation errors"""
    pass


class PricingEstimationService:
    """
    Service class to calculate delivery pricing
    """
    
    @staticmethod
    def estimate_price(
        package_type: str,
        weight: Decimal,
        pickup_city: str,
        pickup_state: str,
        delivery_city: str,
        delivery_state: str,
        service_type: str,
        quantity: int = 1,
        length: Optional[Decimal] = None,
        width: Optional[Decimal] = None,
        height: Optional[Decimal] = None,
    ) -> Dict:
        """
        Calculate the estimated price for a delivery
        """
        
        # Calculate total weight based on quantity
        total_weight = weight * quantity
        
        weight_slab = PricingEstimationService._get_weight_slab(
            package_type, total_weight, length, width, height
        )
        service_pricing = PricingEstimationService._get_service_pricing(service_type)
        pickup_location = PricingEstimationService._get_location_pricing(
            pickup_city, pickup_state
        )
        delivery_location = PricingEstimationService._get_location_pricing(
            delivery_city, delivery_state
        )
        
        # Calculate price components
        base_price = PricingEstimationService._calculate_base_price(
            pickup_location, delivery_location
        )
        weight_charge = weight_slab.extra_charge
        location_multiplier = PricingEstimationService._calculate_location_multiplier(
            pickup_location, delivery_location
        )
        service_multiplier = service_pricing.price_multiplier
        
        # Final price calculation
        subtotal = (base_price + weight_charge) * location_multiplier
        total_price = subtotal * service_multiplier
        
        # Round to 2 decimal places
        total_price = round(float(total_price), 2)
 
        # Response
        return {
            "total_price": total_price,
            "quantity": quantity,
            "weight_per_item": float(weight),
            "total_weight": float(total_weight),
        }
    
    @staticmethod
    def _get_weight_slab(
        package_type: str,
        weight: Decimal,
        length: Optional[Decimal] = None,
        width: Optional[Decimal] = None,
        height: Optional[Decimal] = None,
    ) -> WeightSlab:
        """
        Get the appropriate weight slab for the package
        """

        # Get the smallest weight slab that can accommodate this weight
        weight_slab = WeightSlab.objects.filter(
            package_type=package_type,
            up_to_weight__gte=weight,
            is_active=True
        ).order_by('up_to_weight').first()

        # Check if weight slab exists
        if not weight_slab:
            raise PricingEstimationError(
                f"No pricing configured for {package_type} with weight {weight} kg. "
                f"Please contact support to add pricing for this weight category."
            )
        
        # Validate dimensions if provided (this is the service's unique responsibility)
        if length and width and height:
            user_volume = length * width * height
            
            # Try to find a slab that fits both weight and volume
            # Get all slabs that can accommodate the weight
            available_slabs = WeightSlab.objects.filter(
                package_type=package_type,
                up_to_weight__gte=weight,
                is_active=True,
            ).order_by('up_to_weight')
            
            # Find the first slab that fits the volume
            for slab in available_slabs:
                if slab.validate_dimensions(length, width, height):
                    return slab
            
            # If no slab fits, provide detailed error about volume limits
            max_volume = weight_slab.volume if weight_slab.volume else "not set"
            max_dims = f"{weight_slab.length}×{weight_slab.width}×{weight_slab.height} cm" if weight_slab.length else "not set"
            raise PricingEstimationError(
                f"Package volume ({length}×{width}×{height} cm = {user_volume:.2f} cm³) exceeds "
                f"the maximum allowed volume for all available weight categories. "
                f"Smallest category volume: {max_volume} cm³ (from {max_dims})"
            )
        
        return weight_slab
    
    @staticmethod
    def _get_service_pricing(service_type: str) -> ServiceTypePricing:
        """
        Get the service type pricing
        """
        service_pricing = ServiceTypePricing.objects.filter(
            service_type=service_type,
            is_active=True
        ).first()
        
        if not service_pricing:
            raise PricingEstimationError(
                f"Service type '{service_type}' is not available or not active"
            )
        
        return service_pricing
    
    @staticmethod
    def _get_location_pricing(city: str, state: str) -> LocationPricing:
        """
        Get the location pricing for a city and state
        """
        location_pricing = LocationPricing.objects.filter(
            city__iexact=city.strip(),
            state__iexact=state.strip(),
            is_active=True
        ).first()
        
        if not location_pricing:
            raise PricingEstimationError(
                f"Location '{city}, {state}' is not available or not active"
            )
        
        return location_pricing
    
    @staticmethod
    def _calculate_base_price(
        pickup_location: LocationPricing,
        delivery_location: LocationPricing
    ) -> Decimal:
        """
        Calculate the base price from both locations
        """
        return (pickup_location.base_price + delivery_location.base_price) // 2
    
    @staticmethod
    def _calculate_location_multiplier(
        pickup_location: LocationPricing,
        delivery_location: LocationPricing
    ) -> Decimal:
        """
        Calculate the average location multiplier
        """
        # Average the two location multipliers
        avg_multiplier = (
            pickup_location.price_multiplier + 
            delivery_location.price_multiplier
        ) / 2
        return avg_multiplier