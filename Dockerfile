FROM python:3.9-slim

WORKDIR /app

# Cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy script sinh dữ liệu
COPY generate_data.py .

# Lệnh chạy khi container khởi động
CMD ["python", "generate_data.py"]