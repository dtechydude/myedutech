# Generated by Django 4.2.23 on 2025-07-17 22:12

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BankDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acc_name', models.CharField(max_length=50)),
                ('acc_number', models.CharField(max_length=10)),
                ('bank_name', models.CharField(max_length=50, verbose_name='Bank Name')),
            ],
        ),
    ]
