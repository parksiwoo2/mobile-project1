from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import permissions, viewsets
from .forms import PostForm
from .models import Post
from .serializers import PostSerializer


class BlogImages(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = None

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.pk and not self.request.user.is_staff:
            raise PermissionDenied
        serializer.save()

    def perform_destroy(self, instance):
        if instance.author_id != self.request.user.pk and not self.request.user.is_staff:
            raise PermissionDenied
        instance.delete()


def post_list(request):
    return render(request, "blog/gallery.html", {"posts": Post.objects.all()})


def post_detail(request, pk):
    return render(request, "blog/post_detail.html", {"post": get_object_or_404(Post, pk=pk)})


@login_required
def post_new(request):
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect("post_detail", pk=post.pk)
    return render(request, "blog/post_form.html", {"form": form})


@login_required
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author_id != request.user.pk and not request.user.is_staff:
        raise PermissionDenied
    form = PostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("post_detail", pk=post.pk)
    return render(request, "blog/post_form.html", {"form": form})


def js_test(request):
    return render(request, "blog/js_test.html")
