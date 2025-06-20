from django.db import models
import reversion

DEFAULT_MAX_LENGTH = 255


class Gallery(models.Model):
    name = models.TextField()
    directory = models.CharField(max_length=DEFAULT_MAX_LENGTH, default=".")
    og_url = models.TextField(blank=True, null=True)
    # internet suggests dimensions 1200×630
    og_image = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


@reversion.register()
class Entry(models.Model):
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE)
    basename = models.CharField(max_length=DEFAULT_MAX_LENGTH)
    filenames = models.JSONField(default=list)
    mtimes = models.JSONField(default=list, null=True, blank=True)
    video_mtimes = models.JSONField(default=list, null=True, blank=True)
    order = models.FloatField()
    caption = models.TextField(blank=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    hidden = models.BooleanField(default=False)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    main_thumbnail_path = models.CharField(null=True, blank=True)

    class Meta:
        unique_together = ("gallery", "order")

    def __str__(self):
        return f"{self.id} {self.basename}"
