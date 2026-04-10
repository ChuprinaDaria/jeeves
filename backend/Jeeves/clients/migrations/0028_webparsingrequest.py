# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0027_add_integration_type_to_qrcode'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebParsingRequest',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('website_url', models.URLField(help_text='URL of the website to parse', max_length=500, verbose_name='Website URL')),
                ('description', models.TextField(blank=True, help_text='Description of the parsing request', verbose_name='Description')),
                ('price', models.DecimalField(blank=True, decimal_places=2, help_text='Price for this parsing service (admin only)', max_digits=10, null=True, verbose_name='Price')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed')], default='pending', help_text='Current status of the parsing request', max_length=20, verbose_name='Status')),
                ('path_to_documents', models.CharField(blank=True, help_text='Server URL and directory path where parsed documents are stored (admin only)', max_length=500, verbose_name='Path to Documents')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='web_parsing_requests', to='clients.client', verbose_name='Client')),
                ('knowledge_block', models.ForeignKey(blank=True, help_text='Knowledge block created from this parsing', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='parsing_requests', to='clients.knowledgeblock', verbose_name='Knowledge Block')),
            ],
            options={
                'verbose_name': 'Web Parsing Request',
                'verbose_name_plural': 'Web Parsing Requests',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='webparsingrequest',
            index=models.Index(fields=['client', 'status'], name='clients_web_client__idx'),
        ),
        migrations.AddIndex(
            model_name='webparsingrequest',
            index=models.Index(fields=['status', 'created_at'], name='clients_web_status__idx'),
        ),
    ]

