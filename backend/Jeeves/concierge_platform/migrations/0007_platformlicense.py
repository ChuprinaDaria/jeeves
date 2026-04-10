from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('concierge_platform', '0006_create_langflow_flag'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformLicense',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('license_key', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(
                    choices=[
                        ('missing', 'Missing'),
                        ('valid', 'Valid'),
                        ('grace', 'Grace'),
                        ('expired', 'Expired'),
                    ],
                    default='missing',
                    max_length=10,
                )),
                ('setup_completed_at', models.DateTimeField(blank=True, null=True)),
                ('last_verified_at', models.DateTimeField(blank=True, null=True)),
                ('last_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('gumroad_product_id', models.CharField(blank=True, max_length=100)),
                ('gumroad_purchase_email', models.EmailField(blank=True, max_length=254)),
                ('gumroad_uses', models.IntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Platform License',
                'verbose_name_plural': 'Platform License',
            },
        ),
    ]
