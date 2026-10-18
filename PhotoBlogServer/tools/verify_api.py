import argparse
import http.client
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


def validate_posts(posts):
    if not isinstance(posts, list):
        raise ValueError("응답 본문이 JSON Array가 아닙니다.")
    expected = {"author", "title", "text", "created_date", "published_date", "image"}
    for index, post in enumerate(posts):
        if not isinstance(post, dict) or set(post) != expected:
            raise ValueError(f"{index}번 게시물의 필드가 PDF 규격과 다릅니다.")
        if post["author"] is not None and type(post["author"]) is not int:
            raise ValueError(f"{index}번 게시물의 author 형식이 잘못되었습니다.")
        for field in expected - {"author"}:
            if not isinstance(post[field], str):
                raise ValueError(f"{index}번 게시물의 {field}가 문자열이 아닙니다.")
        for field in ("created_date", "published_date"):
            datetime.fromisoformat(post[field].replace("Z", "+00:00"))
        image = urlsplit(post["image"])
        if image.scheme not in ("http", "https") or not image.netloc:
            raise ValueError(f"{index}번 게시물의 image가 절대 URL이 아닙니다.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir", default="verification")
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.scheme not in ("http", "https") or not url.hostname or url.path not in ("", "/"):
        parser.error("--base-url에는 서버의 HTTP(S) 기본 주소를 입력하세요.")
    headers = {"Accept": "application/json", "Connection": "close"}
    token = os.environ.get("PHOTO_API_TOKEN", "")
    if token:
        headers["Authorization"] = "Token " + token
    connection_class = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(url.hostname, url.port, timeout=15)
    try:
        connection.request("GET", "/api_root/Post/", headers=headers)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        version = "1.1" if response.version == 11 else "1.0"
        response_head = f"HTTP/{version} {response.status} {response.reason}\n" + "\n".join(f"{key}: {value}" for key, value in response.getheaders())
        print("GET /api_root/Post/ HTTP/1.1")
        print(f"Host: {url.netloc}")
        if token:
            print("Authorization: Token [비공개]")
        print("\n" + response_head + "\n\n" + body)
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}: API 요청 실패")
        if "application/json" not in response.getheader("Content-Type", ""):
            raise ValueError("Content-Type이 application/json이 아닙니다.")
        posts = json.loads(body)
        validate_posts(posts)
        destination = Path(args.output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "response.txt").write_text(response_head + "\n\n" + body, encoding="utf-8")
        (destination / "posts.json").write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n검증 성공: HTTP 200 / JSON Array / {len(posts)}개 게시물 / 필드·날짜·이미지 URL 정상")
        if not posts:
            print("빈 배열입니다. 사진을 업로드한 뒤 다시 실행하면 게시물 필드도 검증할 수 있습니다.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
