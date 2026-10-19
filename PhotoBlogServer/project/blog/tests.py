import tempfile
import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, LiveServerTestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from .models import Post


def photo():
    data = BytesIO()
    Image.new("RGB", (32, 32), "skyblue").save(data, "PNG")
    return SimpleUploadedFile("test.png", data.getvalue(), content_type="image/png")


class PostAPITests(APITestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings = override_settings(MEDIA_ROOT=self.directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = get_user_model().objects.create_user("tester", password="test-password")
        self.key = Token.objects.create(user=self.user).key
        self.url = "/api_root/Post/"

    def authorize(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.key)

    def create_post(self, title="서울 여행"):
        self.authorize()
        return self.client.post(self.url, {"title": title, "text": "한강 사진", "image": photo()}, format="multipart")

    def test_pdf_json_array_contract(self):
        response = self.create_post()
        self.assertEqual(response.status_code, 201)
        self.client.credentials()
        listing = self.client.get(self.url, HTTP_HOST="10.0.2.2:8000")
        self.assertEqual(listing.status_code, 200)
        self.assertIsInstance(listing.json(), list)
        self.assertEqual(len(listing.json()), 1)
        post = listing.json()[0]
        self.assertEqual(set(post), {"author", "title", "text", "created_date", "published_date", "image"})
        self.assertEqual(post["author"], self.user.pk)
        self.assertEqual(post["text"], "한강 사진")
        self.assertTrue(post["image"].startswith("http://10.0.2.2:8000/media/blog_image/"))
        self.assertTrue(post["published_date"].endswith("+09:00"))
        self.assertEqual(self.client.get(self.url + str(Post.objects.get().pk) + "/").status_code, 200)
        with Post.objects.get().image.open("rb") as image:
            self.assertEqual(Image.open(image).size, (32, 32))

    def test_head_options_and_get_with_token(self):
        self.create_post()
        head = self.client.head(self.url)
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b"")
        options = self.client.options(self.url)
        self.assertEqual(options.status_code, 200)
        for method in ("GET", "POST", "HEAD", "OPTIONS"):
            self.assertIn(method, options["Allow"])
        self.assertIn("image", options.data["actions"]["POST"])
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_no_pagination_and_empty_array(self):
        self.assertEqual(self.client.get(self.url).json(), [])
        self.create_post()
        original = Post.objects.get()
        Post.objects.bulk_create([Post(title=f"사진 {i}", image=original.image.name, author=self.user) for i in range(21)])
        self.assertEqual(len(self.client.get(self.url).json()), 22)

    def test_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token wrong")
        self.assertEqual(self.client.post(self.url, {}).status_code, 401)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_anonymous_upload_and_write_permissions(self):
        response = self.client.post(self.url, {"title": "익명 사진", "image": photo(), "author": self.user.pk}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["author"])
        post = Post.objects.get()
        self.assertIsNone(post.author)
        url = self.url + str(post.pk) + "/"
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.patch(url, {"title": "변경"}).status_code, 401)
        self.assertEqual(self.client.delete(url).status_code, 401)
        self.authorize()
        self.assertEqual(self.client.patch(url, {"title": "변경"}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.client.patch(url, {"title": "관리자 수정"}).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_author_and_dates_cannot_be_forged(self):
        other = get_user_model().objects.create_user("other")
        self.authorize()
        response = self.client.post(self.url, {"author": other.pk, "created_date": "2000-01-01T00:00:00Z", "published_date": "2000-01-01T00:00:00Z", "title": "작성자", "image": photo()}, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["author"], self.user.pk)
        self.assertFalse(response.data["created_date"].startswith("2000"))
        self.assertFalse(response.data["published_date"].startswith("2000"))

    def test_required_fields(self):
        self.authorize()
        response = self.client.post(self.url, {"title": " "}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data)
        self.assertIn("title", response.data)

    def test_invalid_image_and_long_title(self):
        self.authorize()
        response = self.client.post(self.url, {"title": "a" * 101, "image": SimpleUploadedFile("bad.jpg", b"not an image")}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("image", response.data)
        self.assertIn("title", response.data)

    def test_large_image_rejected(self):
        self.authorize()
        data = photo().read() + b"\0" * (5 * 1024 * 1024)
        response = self.client.post(self.url, {"title": "large", "image": SimpleUploadedFile("large.png", data)}, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("5MB", str(response.data))

    def test_update_delete_and_ownership(self):
        self.create_post()
        url = self.url + str(Post.objects.get().pk) + "/"
        other = get_user_model().objects.create_user("other")
        key = Token.objects.create(user=other).key
        self.client.credentials(HTTP_AUTHORIZATION="Token " + key)
        self.assertEqual(self.client.patch(url, {"title": "denied"}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.authorize()
        self.assertEqual(self.client.patch(url, {"title": "수정"}).data["title"], "수정")
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_browser_pages(self):
        self.create_post("<script>alert(1)</script>")
        post = Post.objects.get()
        self.assertContains(self.client.get("/"), "&lt;script&gt;")
        self.assertNotContains(self.client.get("/"), "<script>alert(1)</script>")
        self.assertContains(self.client.get(f"/post/{post.pk}/"), "한강 사진")
        self.assertContains(self.client.get("/js_test/"), "JSON Array")
        self.assertEqual(self.client.get("/post/new/").status_code, 302)
        self.client.force_login(self.user)
        response = self.client.post("/post/new/", {"title": "웹 게시", "text": "브라우저", "image": photo()})
        self.assertEqual(response.status_code, 302)
        created = Post.objects.get(title="웹 게시")
        self.assertEqual(created.author, self.user)
        response = self.client.post(f"/post/{created.pk}/edit/", {"title": "웹 수정", "text": "내용 변경"})
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.title, "웹 수정")

    def test_web_search_title_text_and_empty_result(self):
        self.create_post("서울 여행")
        original = Post.objects.get()
        Post.objects.create(title="부산", text="해운대", image=original.image.name)
        for term in ("서울", "한강"):
            response = self.client.get("/", {"q": term})
            self.assertEqual([p.pk for p in response.context["posts"]], [original.pk])
        self.assertContains(self.client.get("/", {"q": "없는검색어"}), "검색 결과가 없습니다")
        self.assertEqual(self.client.get("/", {"q": "  "}).context["page_obj"].paginator.count, 2)

    def test_web_sort_and_pagination_preserve_filters(self):
        self.create_post("검색 첫 사진")
        original = Post.objects.get()
        for i in range(7):
            Post.objects.create(title=f"검색 사진 {i}", image=original.image.name, published_date=original.published_date)
        first = self.client.get("/", {"q": "검색", "sort": "oldest"})
        self.assertEqual(len(first.context["posts"]), 6)
        self.assertEqual(first.context["posts"][0].pk, original.pk)
        self.assertContains(first, "sort=oldest&amp;page=2")
        second = self.client.get("/", {"q": "검색", "sort": "oldest", "page": 2})
        self.assertEqual(len(second.context["posts"]), 2)
        newest = self.client.get("/", {"sort": "newest"})
        self.assertEqual(newest.context["posts"][0].pk, Post.objects.latest("pk").pk)
        self.assertEqual(self.client.get("/", {"sort": "invalid", "page": "bad"}).context["sort"], "newest")
        self.assertEqual(self.client.get("/", {"page": 999}).context["page_obj"].number, 2)
        self.assertEqual(len(self.client.get(self.url).json()), 8)

    def test_photo_download_and_missing_file(self):
        self.create_post()
        post = Post.objects.get()
        self.client.credentials()
        response = self.client.get(f"/post/{post.pk}/download/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), photo().read())
        response.close()
        self.assertEqual(self.client.get("/post/99999/download/").status_code, 404)
        post.image.delete(save=False)
        self.assertEqual(self.client.get(f"/post/{post.pk}/download/").status_code, 404)

    def test_web_delete_confirmation_permissions_and_csrf(self):
        self.create_post()
        post = Post.objects.get()
        url = f"/post/{post.pk}/delete/"
        browser = Client(enforce_csrf_checks=True)
        self.assertEqual(browser.get(url).status_code, 302)
        self.assertEqual(browser.post(url).status_code, 403)
        other = get_user_model().objects.create_user("reader")
        browser.force_login(other)
        self.assertEqual(browser.get(url).status_code, 403)
        browser.force_login(self.user)
        self.assertContains(browser.get(url), "삭제 확인")
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
        self.assertEqual(browser.post(url).status_code, 403)
        response = browser.post(url, {"csrfmiddlewaretoken": browser.cookies["csrftoken"].value})
        self.assertRedirects(response, "/")
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())

    def test_staff_can_delete_anonymous_web_post(self):
        post = Post.objects.create(title="익명 사진", image=photo())
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        self.assertContains(self.client.get(f"/post/{post.pk}/"), "삭제")
        self.assertEqual(self.client.post(f"/post/{post.pk}/delete/").status_code, 302)
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())


class HTTPIntegrationTests(LiveServerTestCase):
    def test_android_multipart_and_http_json_verifier(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            boundary = "PhotoBlogIntegrationBoundary"
            body = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\nHTTP 사진\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="text"\r\n\r\nAndroid multipart 형식\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="photo.png"\r\nContent-Type: application/octet-stream\r\n\r\n'
            ).encode("utf-8") + photo().read() + f"\r\n--{boundary}--\r\n".encode()
            request = Request(self.live_server_url + "/api_root/Post/", data=body, headers={
                "Content-Type": "multipart/form-data; boundary=" + boundary,
                "Accept": "application/json",
            })
            with urlopen(request, timeout=10) as response:
                self.assertEqual(response.status, 201)
                self.assertEqual(json.load(response)["text"], "Android multipart 형식")
            script = Path(__file__).resolve().parents[2] / "tools" / "verify_api.py"
            output = Path(directory) / "verification"
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            env.pop("PHOTO_API_TOKEN", None)
            result = subprocess.run([sys.executable, str(script), "--base-url", self.live_server_url, "--output-dir", str(output)], capture_output=True, text=True, encoding="utf-8", env=env, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            posts = json.loads((output / "posts.json").read_text(encoding="utf-8"))
            self.assertEqual(len(posts), 1)
            self.assertIsNone(posts[0]["author"])
            self.assertIn("application/json", (output / "response.txt").read_text(encoding="utf-8"))
