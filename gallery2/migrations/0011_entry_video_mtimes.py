# Generated by Django 5.2 on 2025-06-16 02:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gallery2", "0010_entry_main_thumbnail_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="entry",
            name="video_mtimes",
            field=models.JSONField(blank=True, default=list, null=True),
        ),
    ]
