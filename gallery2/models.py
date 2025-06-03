from django.db import models

DEFAULT_MAX_LENGTH = 255


class Gallery(models.Model):
    name = models.TextField()


class Entry(models.Model):
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE)
    filename = models.CharField(max_length=DEFAULT_MAX_LENGTH)
    order = models.FloatField()
    caption = models.TextField()
