# Sử dụng Python 3.9 slim làm base image
FROM python:3.9-slim

# Cài đặt các phụ thuộc hệ thống cần thiết cho PaddleOCR, OpenCV và pdf2image
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép file requirements và cài đặt dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn vào container
COPY . .

# Tạo thư mục uploads nếu chưa có
RUN mkdir -p uploads

# Biến môi trường
ENV PYTHONUNBUFFERED=1
ENV OLLAMA_HOST=http://ollama:11434

# Mở port 8004
EXPOSE 8004

# Chạy ứng dụng uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
