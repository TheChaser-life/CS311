FROM python:3.10-slim

# 1. Tạo user (Làm ngay từ đầu)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# 2. TỐI ƯU CACHE: Chỉ copy file cài đặt trước
# Để Docker tận dụng Cache: Nếu code đổi mà requirements không đổi thì không cần cài lại
COPY packages.txt requirements.txt ./

# 3. Cài đặt System Packages (Chạy bằng quyền Root)
# Thêm apt-get update để đảm bảo tìm thấy gói
RUN apt-get update && \
    xargs -r apt-get install -y < packages.txt && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 4. Cài đặt Python Packages (Chạy bằng quyền Root)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Bây giờ mới copy toàn bộ Code vào
COPY . .

# 6. Trao quyền sở hữu thư mục cho appuser
# Phải làm bước này SAU KHI copy code, để appuser sở hữu toàn bộ file
RUN chown -R appuser:appuser /app

# 7. Chuyển sang user thường
USER appuser

# 8. Mở cổng
EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]