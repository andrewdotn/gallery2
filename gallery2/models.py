from django.db import models
import reversion

DEFAULT_MAX_LENGTH = 255


class Gallery(models.Model):
    name = models.TextField()
    directory = models.CharField(max_length=DEFAULT_MAX_LENGTH, default=".")

    def __str__(self):
        return self.name


@reversion.register()
class Entry(models.Model):
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE)
    basename = models.CharField(max_length=DEFAULT_MAX_LENGTH)
    filenames = models.JSONField(default=list)
    mtimes = models.JSONField(default=list, null=True, blank=True)
    order = models.FloatField()
    caption = models.TextField(blank=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    hidden = models.BooleanField(default=False)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("gallery", "order")
