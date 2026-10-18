from django.contrib import admin
from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "author", "published_date"]

    def save_model(self, request, obj, form, change):
        if obj.author_id is None:
            obj.author = request.user
        super().save_model(request, obj, form, change)
