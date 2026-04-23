from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_orderrequest_payment_method_and_order_payment_method_choice"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("paid", "Paid"),
                    ("failed", "Failed"),
                    ("refunded", "Refunded"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
