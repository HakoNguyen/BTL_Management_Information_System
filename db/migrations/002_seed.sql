-- Dữ liệu tham chiếu bắt buộc theo đặc tả. Chạy lại nhiều lần không lỗi (test dùng để nạp lại).

-- KH-02: khách lẻ dùng mã mặc định KHLE, không có số điện thoại
INSERT INTO customers (customer_id, full_name, phone, registered_on)
VALUES ('KHLE', 'Khách lẻ', NULL, CURRENT_DATE)
ON CONFLICT (customer_id) DO NOTHING;
