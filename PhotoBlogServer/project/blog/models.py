from django.conf import settings
from django.db import models
from django.utils import timezone


class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=100)
    text = models.TextField(blank=True, max_length=2000)
    image = models.ImageField(upload_to="blog_image/%Y/%m/%d/")
    created_date = models.DateTimeField(default=timezone.now)
    published_date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-published_date", "-id"]

    def __str__(self):
        return self.title
