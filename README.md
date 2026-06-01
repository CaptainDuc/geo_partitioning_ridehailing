# Hệ Thống Phân Mảnh Dữ Liệu Theo Địa Lý (Geo-Partitioning Distributed Database)

Dự án này minh họa các khái niệm cốt lõi của **Cơ sở dữ liệu phân tán (Distributed Database)** thông qua mô hình ứng dụng gọi xe (Grab Clone). Hệ thống tập trung vào việc quản lý dữ liệu tài xế dựa trên vị trí địa lý, tự động di chuyển dữ liệu giữa các máy chủ (shards) khi tài xế di chuyển xuyên biên giới.

---

## 🏗️ Kiến Trúc Hệ Thống

Hệ thống bao gồm 3 thành phần chính hoạt động độc lập:

1.  **API Gateway (Port 5000)**: 
    *   Đóng vai trò là bộ định tuyến (Router) và điều phối trung tâm.
    *   Ẩn đi sự phức tạp của hệ thống phân tán đối với Client.
    *   Quyết định dữ liệu sẽ được ghi vào Shard nào dựa trên logic phân mảnh (Sharding Logic).
    *   Thực hiện cơ chế **Cross-Shard Migration** (di trú dữ liệu giữa các phân mảnh).

2.  **Storage Shards (Port 5001 & 5002)**:
    *   **EU-West (Paris)**: Lưu trữ các tài xế đang hoạt động tại khu vực Paris.
    *   **EU-North (London)**: Lưu trữ các tài xế đang hoạt động tại khu vực London.
    *   Mỗi Shard là một database độc lập (mô phỏng bằng file JSON).

3.  **Visualization Dashboard (Game Canvas)**:
    *   Giao diện web trực quan giúp theo dõi quá trình tài xế di chuyển và cách dữ liệu nhảy giữa các Shard trong thời gian thực.

---

## 📚 Khái Niệm Cơ Sở Dữ Liệu Phân Tán Liên Quan

Trong đề tài này, bạn có thể trình bày các khái niệm sau:

1.  **Horizontal Fragmentation (Phân mảnh ngang)**:
    *   Dữ liệu của bảng `Drivers` không lưu tập trung mà được chia nhỏ theo dòng và đưa về các máy chủ khác nhau.
    *   **Vị trí phân mảnh**: Dựa trên cột `City` (định danh vị trí).

2.  **Geo-Partitioning (Phân mảnh địa lý)**:
    *   Một dạng đặc biệt của Sharding nơi dữ liệu được lưu trữ tại máy chủ gần vị trí địa lý của thực thể đó nhất.
    *   **Lợi ích**: Giảm độ trễ (Latency), tuân thủ chủ quyền dữ liệu (Data Sovereignty).

3.  **Data Migration & Resharding (Di trú dữ liệu)**:
    *   Khi cột phân mảnh (Partition Key - ở đây là `City`) thay đổi, bản ghi phải được di chuyển sang phân mảnh mới tương ứng.
    *   **Quy trình đồng bộ**: Hệ thống sử dụng chiến lược **Insert-First-Delete-Later** (Ghi mới trước, xóa cũ sau) để đảm bảo dữ liệu không bị mất nếu có lỗi mạng xảy ra giữa chừng.

4.  **Transparency (Tính trong suốt)**:
    *   **Location Transparency**: Client chỉ gọi API tại Gateway `/write` mà không cần biết dữ liệu thực sự nằm ở máy chủ 5001 hay 5002. Gateway tự lo việc tìm vị trí.

5.  **Availability vs Consistency (CAP Theorem)**:
    *   Hệ thống ưu tiên tính sẵn sàng (Availability). Khi một Shard chết, các Shard khác vẫn hoạt động bình thường, chỉ vùng bị ảnh hưởng mới không thể truy cập dữ liệu.

---

## 🚀 Hướng Dẫn Chạy Chương Trình

### 1. Chuẩn bị môi trường
Yêu cầu máy cài sẵn Python 3.x và thư viện Flask:
```bash
pip install flask requests
```

### 2. Khởi chạy các thành phần (Chạy trong 3 terminal riêng biệt)

*   **Terminal 1 (Shard EU-West - Paris):**
    ```bash
    python shards/eu_west/app.py
    ```
*   **Terminal 2 (Shard EU-North - London):**
    ```bash
    python shards/eu_north/app.py
    ```
*   **Terminal 3 (API Gateway):**
    ```bash
    python gateway/app.py
    ```

### 3. Trải nghiệm
*   Mở trình duyệt truy cập: `http://localhost:5000/game`
*   **Cách sử dụng**: 
    1. Bấm **"Bắt đầu đồng bộ"**.
    2. Dùng phím **WASD** hoặc chuột để kéo ô tô 🚗 di chuyển.
    3. Khi xe vượt qua ranh giới giữa Paris và London, hãy quan sát **Nhật ký hệ thống** để thấy Gateway thực hiện lệnh `MIGRATED` (Xóa ở shard cũ, thêm vào shard mới).

---

## 🎯 Cách Trình Bày Cho Giảng Viên

1.  **Mở đầu**: Giới thiệu bài toán của Grab khi phải quản lý hàng triệu tài xế trên toàn cầu. Việc dùng 1 database duy nhất sẽ gây nghẽn và chậm.
2.  **Demo**: Chạy giao diện Game, di chuyển xe qua lại ranh giới.
3.  **Giải thích Code**: 
    *   Chỉ vào file `gateway/app.py` hàm `write()`: Giải thích logic kiểm tra vị trí và điều phối.
    *   Chỉ vào các file `storage.json` trong thư mục `shards/`: Cho thấy dữ liệu thực sự biến mất ở file này và xuất hiện ở file kia.
4.  **Kết luận**: Đây là mô hình thu nhỏ của các hệ thống lớn như Google Spanner hoặc CockroachDB trong việc xử lý dữ liệu phân tán theo địa lý.

---
*Người hướng dẫn: Antigravity AI Assistant*
