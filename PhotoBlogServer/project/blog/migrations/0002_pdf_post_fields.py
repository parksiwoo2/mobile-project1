from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


def copy_dates(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    Post.objects.using(schema_editor.connection.alias).update(published_date=models.F("created_date"))


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.RenameField(model_name="post", old_name="content", new_name="text"),
        migrations.RenameField(model_name="post", old_name="created_at", new_name="created_date"),
        migrations.AlterField(model_name="post", name="created_date", field=models.DateTimeField(default=timezone.now)),
        migrations.AddField(model_name="post", name="published_date", field=models.DateTimeField(default=timezone.now)),
        migrations.AddField(model_name="post", name="author", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name="post", name="image", field=models.ImageField(upload_to="blog_image/%Y/%m/%d/")),
        migrations.RunPython(copy_dates, migrations.RunPython.noop),
        migrations.AlterModelOptions(name="post", options={"ordering": ["-published_date", "-id"]}),
    ]
