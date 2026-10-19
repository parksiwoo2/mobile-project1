package com.example.myapplication;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.app.AlertDialog;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {
    private EditText server, title, content;
    private TextView status;
    private RecyclerView posts;
    private TextView selectedName;
    private AlertDialog uploadDialog;
    private Button upload, download, choose, submit;
    private Uri selectedImage;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final ActivityResultLauncher<Intent> picker = registerForActivityResult(
        new ActivityResultContracts.StartActivityForResult(), result -> {
            if (result.getResultCode() == Activity.RESULT_OK && result.getData() != null) {
                selectedImage = result.getData().getData();
                try {
                    getContentResolver().takePersistableUriPermission(selectedImage, Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    if (selectedName != null) selectedName.setText("사진 선택 완료");
                    status.setText("사진 선택 완료 · 제목을 입력하고 업로드하세요.");
                } catch (Exception e) { showError(e); }
            }
        });

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        setContentView(R.layout.activity_main);
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            androidx.core.graphics.Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
        server = findViewById(R.id.server);
        status = findViewById(R.id.textView);
        posts = findViewById(R.id.recyclerView);
        posts.setLayoutManager(new LinearLayoutManager(this));
        posts.setAdapter(new ImageAdapter(new ArrayList<>()));
        upload = findViewById(R.id.btn_save); download = findViewById(R.id.btn_load);
        upload.setOnClickListener(this::onClickUpload);
        download.setOnClickListener(this::onClickDownload);
    }

    private String baseUrl() throws Exception {
        String value = server.getText().toString().trim().replaceAll("/+$", "");
        URL url = new URL(value);
        if ((!url.getProtocol().equals("http") && !url.getProtocol().equals("https"))
                || url.getHost().isEmpty() || !url.getPath().isEmpty()
                || url.getUserInfo() != null || url.getQuery() != null || url.getRef() != null)
            throw new IOException("서버 주소는 https://siwoopark.pythonanywhere.com 형태로 입력하세요.");
        return value;
    }

    public void onClickDownload(View v) {
        final String base;
        try { base = baseUrl(); }
        catch (Exception e) { showError(e); return; }
        busy(true, "동기화 중...");
        worker.execute(() -> {
            try {
                JSONArray rows = new JSONArray(request(base + "/api_root/Post/"));
                List<Bitmap> images = new ArrayList<>();
                int failedImages = 0;
                for (int i = 0; i < rows.length(); i++) {
                    Bitmap bitmap = null;
                    try {
                        HttpURLConnection c = connection(rows.getJSONObject(i).getString("image"));
                        try (InputStream in = c.getInputStream()) {
                            byte[] data = readLimited(in, 5 * 1024 * 1024);
                            BitmapFactory.Options options = new BitmapFactory.Options();
                            options.inJustDecodeBounds = true;
                            BitmapFactory.decodeByteArray(data, 0, data.length, options);
                            options.inSampleSize = 1;
                            while (Math.max(options.outWidth, options.outHeight) / options.inSampleSize > 800) options.inSampleSize *= 2;
                            options.inJustDecodeBounds = false;
                            bitmap = BitmapFactory.decodeByteArray(data, 0, data.length, options);
                        } finally { c.disconnect(); }
                    } catch (Exception ignored) {  }
                    if (bitmap == null) failedImages++;
                    images.add(bitmap);
                }
                final int imageErrors = failedImages;
                runOnUiThread(() -> {
                    if (isDestroyed()) return;
                    try {
                        posts.setAdapter(new ImageAdapter(images));
                        busy(false, rows.length() == 0 ? "불러올 이미지가 없습니다." :
                                imageErrors == 0 ? "이미지 로드 성공! 동기화 완료 · " + images.size() + "개" :
                                "동기화 일부 실패 · " + imageErrors + "개 사진을 불러오지 못했습니다.");
                    } catch (Exception e) { showError(e); }
                });
            } catch (Exception e) { runOnUiThread(() -> showError(e)); }
        });
    }

    public void onClickUpload(View v) {
        View form = getLayoutInflater().inflate(R.layout.dialog_post, null);
        title = form.findViewById(R.id.title); content = form.findViewById(R.id.content);
        selectedName = form.findViewById(R.id.selectedName); choose = form.findViewById(R.id.choose);
        selectedImage = null;
        choose.setOnClickListener(button -> {
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.setType("image/*"); intent.addCategory(Intent.CATEGORY_OPENABLE);
            picker.launch(intent);
        });
        uploadDialog = new AlertDialog.Builder(this).setTitle("새로운 이미지 게시")
                .setView(form).setNegativeButton("취소", null).setPositiveButton("게시", null).create();
        uploadDialog.setOnShowListener(dialog -> {
            submit = uploadDialog.getButton(AlertDialog.BUTTON_POSITIVE);
            submit.setOnClickListener(button -> submitPost());
        });
        uploadDialog.show();
    }

    private void submitPost() {
        final String base, heading = title.getText().toString().trim(), body = content.getText().toString();
        final Uri photo = selectedImage;
        try {
            base = baseUrl();
            if (heading.isEmpty() || photo == null) throw new IOException("제목과 사진을 입력하세요.");
        } catch (Exception e) { showError(e); return; }
        busy(true, "업로드 중...");
        worker.execute(() -> {
            try {
                byte[] image;
                try (InputStream in = getContentResolver().openInputStream(photo)) { image = readLimited(in, 5 * 1024 * 1024); }
                String boundary = "PhotoBlog" + System.nanoTime();
                HttpURLConnection c = connection(base + "/api_root/Post/");
                try {
                    c.setRequestMethod("POST"); c.setDoOutput(true);
                    c.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
                    try (OutputStream out = c.getOutputStream()) {
                        field(out, boundary, "title", heading); field(out, boundary, "text", body);
                        write(out, "--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"photo.jpg\"\r\nContent-Type: application/octet-stream\r\n\r\n");
                        out.write(image); write(out, "\r\n--" + boundary + "--\r\n");
                    }
                    response(c);
                } finally { c.disconnect(); }
                runOnUiThread(() -> {
                    if (isDestroyed()) return;
                    selectedImage = null; busy(false, "업로드 완료");
                    uploadDialog.dismiss();
                    Toast.makeText(this, "Upload 완료", Toast.LENGTH_LONG).show();
                    onClickDownload(null);
                });
            } catch (Exception e) { runOnUiThread(() -> showError(e)); }
        });
    }

    private HttpURLConnection connection(String address) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(address).openConnection();
        c.setConnectTimeout(10000); c.setReadTimeout(15000); c.setInstanceFollowRedirects(false);
        c.setRequestProperty("Accept", "application/json"); return c;
    }
    private String request(String address) throws Exception {
        HttpURLConnection c = connection(address);
        try { return response(c); } finally { c.disconnect(); }
    }
    private String response(HttpURLConnection c) throws Exception {
        int code = c.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? c.getInputStream() : c.getErrorStream();
        String text = "";
        if (stream != null) try (InputStream in = stream) { text = new String(readLimited(in, 1024 * 1024), StandardCharsets.UTF_8); }
        if (code < 200 || code >= 300) throw new IOException("HTTP " + code + " · " + text.substring(0, Math.min(300, text.length())));
        return text;
    }
    private byte[] readLimited(InputStream in, int limit) throws IOException {
        if (in == null) throw new IOException("파일을 열 수 없습니다.");
        ByteArrayOutputStream out = new ByteArrayOutputStream(); byte[] buffer = new byte[8192]; int n;
        while ((n = in.read(buffer)) != -1) { if (out.size() + n > limit) throw new IOException("파일 또는 응답 크기가 너무 큽니다. 사진은 5MB 이하로 선택하세요."); out.write(buffer, 0, n); }
        return out.toByteArray();
    }
    private void write(OutputStream out, String text) throws IOException { out.write(text.getBytes(StandardCharsets.UTF_8)); }
    private void field(OutputStream out, String boundary, String name, String value) throws IOException {
        write(out, "--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + name + "\"\r\n\r\n" + value + "\r\n");
    }
    private void busy(boolean value, String message) {
        if (isDestroyed()) return;
        upload.setEnabled(!value); download.setEnabled(!value);
        server.setEnabled(!value);
        if (uploadDialog != null && uploadDialog.isShowing()) {
            choose.setEnabled(!value); submit.setEnabled(!value);
            title.setEnabled(!value); content.setEnabled(!value);
            uploadDialog.setCancelable(!value);
            uploadDialog.getButton(AlertDialog.BUTTON_NEGATIVE).setEnabled(!value);
        }
        status.setText(message);
    }
    private void showError(Exception e) {
        if (isDestroyed()) return;
        busy(false, "오류 · " + e.getMessage());
        if (uploadDialog != null && uploadDialog.isShowing()) selectedName.setText("오류 · " + e.getMessage());
    }
    @Override protected void onDestroy() { worker.shutdownNow(); super.onDestroy(); }
}
