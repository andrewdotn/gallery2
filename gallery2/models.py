from django.db import models

DEFAULT_MAX_LENGTH = 255


class Gallery(models.Model):
    name = models.TextField()
    directory = models.CharField(max_length=DEFAULT_MAX_LENGTH)


class Entry(models.Model):
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE)
    basename = models.CharField(max_length=DEFAULT_MAX_LENGTH)
    filenames = models.JSONField(default=list)
    order = models.FloatField()
    caption = models.TextField()
    timestamp = models.DateTimeField(null=True, blank=True)
