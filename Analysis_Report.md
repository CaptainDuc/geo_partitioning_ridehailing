# BÁO CÁO PHÂN TÍCH HỆ THỐNG CƠ SỞ DỮ LIỆU PHÂN TÁN (NÂNG CAO)
## CHỦ ĐỀ: GEO-PARTITIONING & SHARD MIGRATION

**Học viên:** Trần Minh Đức
**Đề tài:** Hệ thống quản lý tài xế Grab thông minh - Mô hình phân mảnh địa lý.  
**Cơ sở lý thuyết:** M. Tamer Özsu & Patrick Valduriez.

---

### 1. Thiết kế Phân mảnh & Cấp phát (Fragmentation & Allocation)
Theo Özsu & Valduriez, thiết kế DDB bao gồm 2 bước quan trọng:
- **Phân mảnh (Fragmentation)**: Hệ thống sử dụng **Phân mảnh ngang sơ cấp (Primary Horizontal Fragmentation)**.
    - **Lý do**: Việc phân chia dữ liệu dựa trên chính các thuộc tính (vị từ) của bảng `Drivers` (cụ thể là cột `City`), không phụ thuộc vào bảng khác.
    - **Lợi ích**: Giảm thiểu việc di chuyển dữ liệu qua mạng khi thực hiện các truy vấn cục bộ (Local Queries).
- **Cấp phát (Allocation)**: Dữ liệu được cấp phát theo mô hình **Không nhân bản (Non-redundant allocation)** trong bản demo này để tối ưu hóa không gian lưu trữ và tránh xung đột cập nhật đơn giản.

### 2. Xử lý và Định vị Truy vấn (Distributed Query Processing)
Một điểm cốt lõi trong lý thuyết Özsu là quá trình **Localization (Định vị)**:
- **Cơ chế định tuyến**: Gateway thực hiện chức năng của bộ tối ưu hóa truy vấn phân tán (Distributed Query Optimizer). 
- **Lược đồ (Schema)**: Gateway giữ một "Global Schema" (danh sách các Shard và điều kiện `City`). 
- **Tối ưu hóa**: Thay vì gửi truy vấn đến tất cả các node (Broadcast), Gateway thực hiện **Query Pruning** (Cắt tỉa truy vấn), chỉ gửi yêu cầu đến Shard chứa dữ liệu mục tiêu. Điều này làm giảm lưu lượng mạng tối đa.

### 3. Di trú dữ liệu & Tính nguyên tử (Shard Migration & Atomicity)
Việc di chuyển tài xế giữa các Shard là một **Giao dịch phân tán (Distributed Transaction)** phức tạp:
- **Nguyên tắc Tách biệt (Disjointness)**: Theo lý thuyết, tại trạng thái nghỉ, mỗi tài xế chỉ thuộc về một phân mảnh duy nhất.
- **Trạng thái chuyển tiếp (Transitional State)**: Để đảm bảo **Độ tin cậy (Reliability)**, hệ thống chấp nhận một sự vi phạm tạm thời tính tách biệt:
    - **Cơ chế**: Dữ liệu sẽ tồn tại song song ở cả 2 Shard trong một khoảng thời gian cực ngắn (giữa bước Insert và bước Delete).
    - **Lý do**: Tránh kịch bản "Mất dữ liệu" (Data Loss) nếu hệ thống bị ngắt kết nối sau khi xóa ở node cũ nhưng chưa kịp ghi vào node mới.
- **Tính nguyên tử (Atomicity)**: Hệ thống cố gắng đạt được tính nguyên tử bằng cách đảm bảo nếu bước Ghi (Insert) thất bại, dữ liệu gốc vẫn được bảo toàn tại Shard cũ.

### 4. Kiểm soát Truy cập đồng thời (Concurrency Control)
Theo lý thuyết phân tán, việc quản lý nhiều phiên làm việc cùng lúc là rất quan trọng:
- **Cơ chế áp dụng**: Hệ thống sử dụng mô hình **Tự chủ cục bộ (Local Autonomy)**. Mỗi Shard tự quản lý việc khóa dữ liệu (Locking) hoặc đánh dấu thời gian (Timestamping) cho file JSON của mình.
- **Tính nhất quán (Eventual Consistency)**: Hệ thống không áp dụng các cơ chế khóa toàn cục để tránh làm giảm hiệu năng. Trong quá trình di trú, trạng thái nhất quán tuyệt đối có thể bị phá vỡ tạm thời, nhưng hệ thống sẽ tự động hội tụ về trạng thái đúng sau khi các lệnh xóa hoàn tất.
- **Tối ưu hóa**: Phù hợp với đặc thù ứng dụng gọi xe, nơi sự sai lệch vị trí trong vài mili giây có thể chấp nhận được để đổi lấy tốc độ phản hồi cực nhanh.

### 5. Phân tích theo định lý CAP
Dựa trên tam giác CAP được trình bày trong giáo trình Özsu:
- **Partition Tolerance (P)**: Được ưu tiên hàng đầu, hệ thống chấp nhận mạng bị phân tách.
- **Availability (A)**: Cao, người dùng vẫn có thể truy cập các shard còn sống.
- **Consistency (C)**: Hệ thống đạt mức **Eventual Consistency (Nhất quán sau cùng)**. Đây là sự lựa chọn phổ biến trong các kiến trúc NoSQL và hệ thống phân tán quy mô lớn để tối ưu hóa hiệu năng thay vì chọn Strong Consistency (Nhất quán tức thì).

### 6. Đề xuất mở rộng (Future Improvements)
Để đạt đến một hệ thống phân tán hoàn hảo theo Özsu:
- **Replication (Nhân bản)**: Cần thêm các Shard dự phòng (Secondary Shards) cho mỗi khu vực để đảm bảo dữ liệu không bị mất nếu ổ cứng node đó bị hỏng.
- **Global Concurrency Control**: Triển khai máy chủ quản lý khóa tập trung hoặc thuật toán bầu chọn (Election Algorithm) để quản lý các giao dịch phức tạp hơn.