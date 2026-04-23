from django.test import TestCase
from decimal import Decimal

from pricings.models import WeightSlab


class WeightSlabValidationTests(TestCase):
	def setUp(self):
		self.slab = WeightSlab(
			package_type=WeightSlab.PackageType.PACKAGE,
			up_to_weight=Decimal("5.00"),
			length=Decimal("10.00"),
			width=Decimal("10.00"),
			height=Decimal("10.00"),
		)

	def test_validate_dimensions_rejects_volume_above_slab_limit(self):
		is_valid = self.slab.validate_dimensions(
			user_length=Decimal("11.00"),
			user_width=Decimal("10.00"),
			user_height=Decimal("10.00"),
		)

		self.assertFalse(is_valid)


	def test_volume_returns_none_when_any_dimension_missing(self):
		slab_without_height = WeightSlab(
			package_type=WeightSlab.PackageType.PACKAGE,
			up_to_weight=Decimal("5.00"),
			length=Decimal("10.00"),
			width=Decimal("10.00"),
		)

		self.assertIsNone(slab_without_height.volume)