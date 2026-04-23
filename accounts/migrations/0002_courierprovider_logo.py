from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='courierprovider',
            name='logo',
            field=models.ImageField(
                blank=True,
                help_text='Optional courier company logo',
                null=True,
                upload_to='courier_providers/logos/',
            ),
        ),
    ]
