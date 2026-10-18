from django import forms
from rest_framework.exceptions import ValidationError as APIValidationError
from .models import Post
from .serializers import PostSerializer


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "text", "image"]
        labels = {"title": "제목", "text": "내용", "image": "사진"}

    def clean_image(self):
        image = self.cleaned_data["image"]
        if "image" in self.files:
            try:
                PostSerializer().validate_image(image)
            except APIValidationError as error:
                raise forms.ValidationError(error.detail) from error
        return image
