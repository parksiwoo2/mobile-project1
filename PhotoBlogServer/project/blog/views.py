from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.views.decorators.http import require_http_methods
from pathlib import Path
from urllib.parse import urlencode
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import permissions, viewsets
from .forms import PostForm
from .models import Post
from .serializers import PostSerializer


class BlogImages(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve", "create", "metadata"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        author = self.request.user if self.request.user.is_authenticated else None
        serializer.save(author=author)

    def perform_update(self, serializer):
        if serializer.instance.author_id != self.request.user.pk and not self.request.user.is_staff:
            raise PermissionDenied
        serializer.save()

    def perform_destroy(self, instance):
        if instance.author_id != self.request.user.pk and not self.request.user.is_staff:
            raise PermissionDenied
        instance.delete()


def post_list(request):
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "newest")
    if sort not in ("newest", "oldest"):
        sort = "newest"
    posts = Post.objects.all()
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(text__icontains=query))
    posts = posts.order_by("published_date", "id") if sort == "oldest" else posts.order_by("-published_date", "-id")
    page = Paginator(posts, 6).get_page(request.GET.get("page"))
    return render(request, "blog/gallery.html", {
        "posts": page, "page_obj": page, "query": query, "sort": sort,
        "page_query": urlencode({"q": query, "sort": sort}),
    })


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


@require_http_methods(["GET", "HEAD"])
def post_download(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if not post.image:
        raise Http404("사진이 없습니다.")
    try:
        image = post.image.open("rb")
    except FileNotFoundError:
        raise Http404("사진 파일을 찾을 수 없습니다.")
    return FileResponse(image, as_attachment=True, filename=Path(post.image.name).name)


@login_required
@require_http_methods(["GET", "POST"])
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author_id != request.user.pk and not request.user.is_staff:
        raise PermissionDenied
    if request.method == "POST":
        post.delete()
        return redirect("post_list")
    return render(request, "blog/post_confirm_delete.html", {"post": post})
