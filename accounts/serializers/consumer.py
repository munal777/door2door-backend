from rest_framework import serializers

from accounts.models import Address


class AddressSerializer(serializers.ModelSerializer):
	"""Serializer for consumer address operations."""

	class Meta:
		model = Address
		fields = [
			'id',
			'label',
			'address_line',
			'landmark',
			'city',
			'state',
			'latitude',
			'longitude',
			'is_default',
			'created_at',
			'updated_at',
		]
		read_only_fields = ['id', 'created_at', 'updated_at']

	def validate_label(self, value):
		label = value.strip()
		request = self.context.get('request')
		user = getattr(self.instance, 'user', None)

		if user is None and request and request.user and request.user.is_authenticated:
			user = request.user

		if user is None:
			return label

		existing_addresses = Address.objects.filter(user=user, label=label)
		if self.instance:
			existing_addresses = existing_addresses.exclude(pk=self.instance.pk)

		if existing_addresses.exists():
			raise serializers.ValidationError(
				f"You already have a saved address with label '{label}'."
			)

		return label

	def create(self, validated_data):
		request = self.context.get('request')
		if not request or not request.user or not request.user.is_authenticated:
			raise serializers.ValidationError('Authenticated user is required to save address.')

		user = request.user
		if not user.addresses.exists():
			validated_data['is_default'] = True

		return Address.objects.create(user=user, **validated_data)
