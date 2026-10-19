package com.example.myapplication;

import android.graphics.Bitmap;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import java.util.List;

public class ImageAdapter extends RecyclerView.Adapter<ImageAdapter.ImageViewHolder> {
    private final List<Bitmap> imageList;

    public ImageAdapter(List<Bitmap> imageList) {
        this.imageList = imageList;
    }

    @NonNull
    @Override public ImageViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_image, parent, false);
        return new ImageViewHolder(view);
    }

    @Override public void onBindViewHolder(@NonNull ImageViewHolder holder, int position) {
        Bitmap image = imageList.get(position);
        holder.imageView.setImageBitmap(image);
        holder.imageView.setContentDescription("게시물 사진 " + (position + 1));
        holder.error.setVisibility(image == null ? View.VISIBLE : View.GONE);
    }

    @Override public int getItemCount() { return imageList.size(); }

    public static class ImageViewHolder extends RecyclerView.ViewHolder {
        final ImageView imageView;
        final TextView error;
        public ImageViewHolder(View itemView) {
            super(itemView);
            imageView = itemView.findViewById(R.id.imageViewItem);
            error = itemView.findViewById(R.id.imageError);
        }
    }
}
