import json
import time
import random
from faker import Faker
from kafka import KafkaProducer
from kafka.errors import KafkaError

fake = Faker()

KAFKA_BROKER_URL = 'kafka:9093' # Địa chỉ Kafka broker nội bộ trong Docker network
TRANSACTIONS_TOPIC = 'transactions'
TRANSACTIONS_PER_SECOND = 5 # Số giao dịch sinh ra mỗi giây

def create_kafka_producer():
    """Tạo Kafka producer, thử kết nối lại nếu thất bại."""
    producer = None
    while producer is None:
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKER_URL,
                value_serializer=lambda v: json.dumps(v).encode('utf-8') # Serialize dữ liệu thành JSON UTF-8
            )
            print("Kafka Producer đã kết nối thành công!")
        except KafkaError as e:
            print(f"Lỗi kết nối Kafka: {e}. Thử lại sau 5 giây...")
            time.sleep(5)
    return producer

def generate_transaction():
    """Tạo một giao dịch giả lập."""
    return {
        'transaction_id': fake.uuid4(),
        'user_id': fake.random_int(min=1000, max=9999),
        'amount': round(random.uniform(10.0, 20000000.0), 2), # Số tiền giao dịch
        'currency': 'VND',
        'timestamp': int(time.time() * 1000), # Milliseconds timestamp
        'location': fake.city(),
        'merchant_id': fake.random_int(min=100, max=999),
        # Thêm các trường dữ liệu khác nếu cần
    }

def send_transaction(producer, topic, transaction_data):
    """Gửi giao dịch đến Kafka topic."""
    try:
        future = producer.send(topic, value=transaction_data)
        # Block đợi gửi thành công (tùy chọn)
        # record_metadata = future.get(timeout=10)
        # print(f"Đã gửi thông điệp đến topic {record_metadata.topic} partition {record_metadata.partition}")
        producer.flush() # Đảm bảo message được gửi đi
    except KafkaError as e:
        print(f"Lỗi khi gửi message: {e}")
    except Exception as e:
        print(f"Lỗi không xác định: {e}")


if __name__ == "__main__":
    kafka_producer = create_kafka_producer()
    if kafka_producer:
        print(f"Bắt đầu sinh dữ liệu vào topic '{TRANSACTIONS_TOPIC}'...")
        while True:
            transaction = generate_transaction()
            print(f"Sinh giao dịch: {transaction}")
            send_transaction(kafka_producer, TRANSACTIONS_TOPIC, transaction)
            time.sleep(1.0 / TRANSACTIONS_PER_SECOND)
    else:
        print("Không thể tạo Kafka Producer. Thoát.")