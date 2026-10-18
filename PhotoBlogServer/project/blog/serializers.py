from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ["author", "title", "text", "created_date", "published_date", "image"]
        read_only_fields = ["author", "created_date", "published_date"]

    def validate_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("사진은 5MB 이하만 가능합니다.")
        if value.image.format not in ("JPEG", "PNG", "WEBP"):
            raise serializers.ValidationError("JPEG, PNG, WEBP 사진만 가능합니다.")
        if value.image.width * value.image.height > 20_000_000:
            raise serializers.ValidationError("사진은 2천만 화소 이하만 가능합니다.")
        return value
