# Generated by Django 5.2 on 2025-06-15 23:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gallery2", "0009_entry_mtimes"),
    ]

    operations = [
        migrations.AddField(
            model_name="entry",
            name="main_thumbnail_path",
            field=models.CharField(blank=True, null=True),
        ),
    ]
