# HƯỚNG DẪN CHI TIẾT: CÁC QUY TẮC CƠ SỞ DỮ LIỆU PHÂN TÁN (THEO ÖZSU & VALDURIEZ)
## Đề tài: Hệ thống Geo-Partitioning cho ứng dụng gọi xe

Tài liệu này cung cấp các luận cứ khoa học cho dự án của bạn, giúp bạn trả lời các câu hỏi hóc búa từ giảng viên về kiến trúc hệ thống.

---

### Quy tắc 1: Tính tự chủ cục bộ (Local Autonomy)
*   **Lý thuyết**: Các phân mảnh tại các vị trí khác nhau phải có khả năng hoạt động độc lập. Dữ liệu tại Shard Paris phải được quản lý bởi Shard Paris, không phụ thuộc vào tình trạng của Shard London.
*   **Áp dụng vào dự án**:
    - Mỗi Shard của bạn là một server Flask riêng biệt với file `storage.json` riêng.
    - Nếu Gateway hoặc Shard London bị lỗi, dữ liệu tại Paris vẫn có thể được truy xuất cục bộ (nếu kết nối trực tiếp). Điều này đảm bảo tính "sống còn" của dữ liệu khu vực.

### Quy tắc 2: Không phụ thuộc vào một vị trí trung tâm (No Reliance on a Central Site)
*   **Lý thuyết**: Một hệ thống phân tán thực thụ không nên dựa dẫm hoàn toàn vào một node trung tâm duy nhất để tránh điểm chết (Single Point of Failure).
*   **Áp dụng vào dự án**:
    - Mặc dù bạn dùng API Gateway để điều hướng, nhưng **dữ liệu thực tế** không nằm ở Gateway. Gateway chỉ giữ logic điều hướng.
    - Trong thực tế (Özsu), logic này có thể được nhân bản ở nhiều Gateway khác nhau để tăng tính chịu lỗi.

### Quy tắc 3: Tính độc lập với sự phân mảnh (Fragmentation Independence)
*   **Lý thuyết**: Người dùng hoặc ứng dụng (Client) không cần biết dữ liệu bị chia nhỏ như thế nào. Họ chỉ cần thấy một view duy nhất của bảng dữ liệu.
*   **Áp dụng vào dự án**:
    - Giao diện Game (Frontend) chỉ gọi API `/write` hoặc `/api/overview`. Nó không cần quan tâm tài xế A nằm ở file JSON nào. 
    - Việc "lắp ghép" các mảnh dữ liệu từ nhiều Shard để hiển thị lên bản đồ chính là minh chứng cho tính trong suốt này.

### Quy tắc 4: Tính độc lập vị trí (Location Independence/Transparency)
*   **Lý thuyết**: Người dùng không cần biết dữ liệu được lưu trữ vật lý ở đâu (IP nào, Port nào).
*   **Áp dụng vào dự án**:
    - Gateway đóng vai trò "Location Server". Khi xe di chuyển, Gateway tự tìm port 5001 hay 5002. Client hoàn toàn "mù tịt" về sự tồn tại của các port này, tạo ra trải nghiệm liền mạch.

### Quy tắc 5: Xử lý giao dịch phân tán (Distributed Transaction Management)
*   **Lý thuyết**: Đảm bảo tính ACID xuyên suốt các máy chủ. Đây là phần khó nhất trong lý thuyết của Özsu và Valduriez.
*   **Áp dụng vào dự án (Cực kỳ quan trọng để trình bày)**:
    - **Vấn đề**: Khi di chuyển tài xế từ Paris sang London, ta cần thực hiện 2 hành động: Xóa ở cũ và Thêm ở mới. Nếu đang xóa mà mất mạng không thêm được -> Mất dữ liệu.
    - **Giải pháp của bạn (Atomic Commit Simulation)**: Bạn sử dụng kỹ thuật **Insert-First-Delete-Later**.
      1. Bước 1: Ghi vào Shard mới (Target).
      2. Bước 2: Chỉ khi bước 1 phản hồi "Success", Gateway mới ra lệnh xóa (Delete) ở Shard cũ.
    - **Lý luận**: Đây là một dạng rút gọn của giao thức **Two-Phase Commit (2PC)** giúp đảm bảo dữ liệu luôn có ít nhất một bản sao an toàn trong quá trình di trú.

### Quy tắc 6: Độc lập với phần cứng và hệ điều hành
*   **Lý thuyết**: Hệ thống phân tán có thể chạy trên các node có cấu hình khác nhau.
*   **Áp dụng vào dự án**:
    - Các Shard của bạn có thể chạy trên Windows, Linux hoặc Docker container mà không ảnh hưởng đến logic định tuyến của Gateway.

---

## CÁC CÂU HỎI GIẢNG VIÊN CÓ THỂ HỎI (DỰA TRÊN LÝ THUYẾT ÖZSU)

**1. Tại sao em lại chọn phân mảnh ngang (Horizontal) mà không phải phân mảnh dọc (Vertical)?**
*   *Trả lời*: Vì trong ứng dụng gọi xe, chúng ta quản lý các tập thực thể (tài xế) riêng biệt theo vùng. Phân mảnh ngang giúp truy vấn tất cả thuộc tính của 1 tài xế nhanh nhất tại server gần họ nhất.

**2. Nếu Gateway của em bị sập thì sao?**
*   *Trả lời*: Đây là điểm yếu Single Point of Failure trong mô hình demo. Trong thực tế theo Özsu, chúng ta sẽ sử dụng cơ chế **Distributed Metadata Management**, nơi các node có thể tự trao đổi thông tin cấu hình với nhau thông qua các thuật toán như Gossip Protocol thay vì qua một Gateway duy nhất.

**3. Làm sao em đảm bảo tính nhất quán (Consistency) khi di chuyển dữ liệu?**
*   *Trả lời*: Em sử dụng chiến lược "Ghi trước, Xóa sau" và kiểm tra mã phản hồi HTTP từ các Shard. Nếu Shard mới không phản hồi 200 OK, quá trình di chuyển sẽ dừng lại và dữ liệu ở Shard cũ vẫn được giữ nguyên, đảm bảo không bao giờ bị mất dữ liệu giữa chừng.

---
*Tài liệu này được biên soạn để hỗ trợ sinh viên nắm vững lý thuyết Cơ sở dữ liệu phân tán áp dụng vào thực tế.*
