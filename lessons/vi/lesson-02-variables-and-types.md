---
title: "Bài 2: Biến và Kiểu Dữ Liệu"
language: vi
level: beginner
tags: [rust, variables, types, basics]
---

# Bài 2: Biến và Kiểu Dữ Liệu

## Giới thiệu

Trong bài học này, chúng ta sẽ tìm hiểu về biến, kiểu dữ liệu và một trong những đặc điểm quan trọng nhất của Rust: tính bất biến (immutability) mặc định.

## Mục tiêu học tập

Sau khi hoàn thành bài học này, bạn sẽ có thể:
- Khai báo và sử dụng biến trong Rust
- Hiểu về tính bất biến và khả biến
- Làm việc với các kiểu dữ liệu cơ bản
- Sử dụng type annotation
- Hiểu về shadowing

## Khai báo biến

### Biến bất biến (Immutable)

Mặc định, tất cả biến trong Rust đều bất biến:

```rust
fn main() {
    let x = 5;
    println!("Giá trị của x là: {}", x);
    
    // Lỗi: không thể thay đổi giá trị
    // x = 6;
}
```

### Biến khả biến (Mutable)

Sử dụng từ khóa `mut` để tạo biến có thể thay đổi:

```rust
fn main() {
    let mut y = 5;
    println!("Giá trị ban đầu: {}", y);
    
    y = 6;
    println!("Giá trị mới: {}", y);
}
```

## Kiểu dữ liệu cơ bản

### Số nguyên (Integers)

```rust
fn main() {
    let a: i32 = 42;        // Số nguyên có dấu 32-bit
    let b: u32 = 100;       // Số nguyên không dấu 32-bit
    let c: i64 = -1000;     // Số nguyên có dấu 64-bit
    let d: u8 = 255;        // Số nguyên không dấu 8-bit
    
    println!("a={}, b={}, c={}, d={}", a, b, c, d);
}
```

**Các kiểu số nguyên:**
- `i8`, `i16`, `i32`, `i64`, `i128` - có dấu
- `u8`, `u16`, `u32`, `u64`, `u128` - không dấu
- `isize`, `usize` - phụ thuộc vào kiến trúc hệ thống

### Số thực (Floating-point)

```rust
fn main() {
    let x: f32 = 3.14;      // 32-bit
    let y: f64 = 2.71828;   // 64-bit (mặc định)
    
    println!("x={}, y={}", x, y);
}
```

### Boolean

```rust
fn main() {
    let is_active: bool = true;
    let is_complete = false;  // Type inference
    
    println!("Active: {}, Complete: {}", is_active, is_complete);
}
```

### Ký tự (Character)

```rust
fn main() {
    let letter: char = 'A';
    let emoji = '😀';
    let vietnamese = 'ế';
    
    println!("Ký tự: {}, {}, {}", letter, emoji, vietnamese);
}
```

**Lưu ý:** `char` trong Rust là Unicode Scalar Value, chiếm 4 bytes.

## Type Annotation và Type Inference

### Type Inference (Suy luận kiểu)

Rust có thể tự động suy luận kiểu dữ liệu:

```rust
fn main() {
    let x = 5;           // Rust suy luận x là i32
    let y = 3.14;        // Rust suy luận y là f64
    let is_true = true;  // Rust suy luận là bool
}
```

### Type Annotation (Chỉ định kiểu)

Bạn có thể chỉ định kiểu rõ ràng:

```rust
fn main() {
    let x: i64 = 5;
    let y: f32 = 3.14;
    let name: &str = "Rust";
}
```

## Shadowing

Shadowing cho phép khai báo lại biến với cùng tên:

```rust
fn main() {
    let x = 5;
    println!("x = {}", x);
    
    let x = x + 1;  // Shadow biến x
    println!("x = {}", x);
    
    let x = x * 2;  // Shadow lại lần nữa
    println!("x = {}", x);
}
```

### Shadowing vs Mutable

Shadowing khác với mutable:

```rust
fn main() {
    // Shadowing: có thể thay đổi kiểu
    let spaces = "   ";
    let spaces = spaces.len();
    
    // Mutable: không thể thay đổi kiểu
    let mut count = "   ";
    // count = count.len();  // LỖI!
}
```

## Hằng số (Constants)

Hằng số luôn bất biến và phải có type annotation:

```rust
const MAX_POINTS: u32 = 100_000;
const PI: f64 = 3.14159265359;

fn main() {
    println!("Điểm tối đa: {}", MAX_POINTS);
    println!("Pi: {}", PI);
}
```

**Quy tắc đặt tên hằng số:**
- Viết HOA toàn bộ
- Sử dụng dấu gạch dưới `_` để phân tách từ
- Phải khai báo kiểu dữ liệu

## Tuple

Tuple nhóm nhiều giá trị với các kiểu khác nhau:

```rust
fn main() {
    let person: (&str, i32, f64) = ("An", 25, 1.75);
    
    // Truy cập bằng index
    println!("Tên: {}", person.0);
    println!("Tuổi: {}", person.1);
    println!("Chiều cao: {}m", person.2);
    
    // Destructuring
    let (name, age, height) = person;
    println!("{} {} tuổi, cao {}m", name, age, height);
}
```

## Array

Array có kích thước cố định và cùng kiểu dữ liệu:

```rust
fn main() {
    let numbers: [i32; 5] = [1, 2, 3, 4, 5];
    
    println!("Phần tử đầu: {}", numbers[0]);
    println!("Phần tử cuối: {}", numbers[4]);
    
    // Tạo array với giá trị giống nhau
    let zeros = [0; 10];  // [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    println!("Độ dài: {}", zeros.len());
}
```

## Bài tập thực hành

### Bài tập 1: Chuyển đổi nhiệt độ

```rust
fn main() {
    let celsius: f64 = 25.0;
    let fahrenheit = celsius * 9.0 / 5.0 + 32.0;
    
    println!("{}°C = {}°F", celsius, fahrenheit);
}
```

### Bài tập 2: Tính diện tích hình chữ nhật

```rust
fn main() {
    let width = 10;
    let height = 5;
    let area = width * height;
    
    println!("Diện tích: {} x {} = {}", width, height, area);
}
```

### Bài tập 3: Làm việc với tuple

```rust
fn main() {
    let student = ("Minh", 20, 8.5);
    let (name, age, gpa) = student;
    
    println!("Sinh viên: {}", name);
    println!("Tuổi: {}", age);
    println!("Điểm TB: {}", gpa);
}
```

## Lỗi thường gặp

### 1. Thay đổi biến bất biến

```rust
// SAI
let x = 5;
x = 6;  // Lỗi!

// ĐÚNG
let mut x = 5;
x = 6;
```

### 2. Quên type annotation cho hằng số

```rust
// SAI
const MAX = 100;  // Lỗi!

// ĐÚNG
const MAX: i32 = 100;
```

### 3. Truy cập array ngoài phạm vi

```rust
let arr = [1, 2, 3];
// let x = arr[5];  // Panic tại runtime!
```

## Kiểm tra kiến thức

1. Biến nào sau đây có thể thay đổi giá trị?
   - A) `let x = 5;`
   - B) `let mut x = 5;`
   - C) `const X: i32 = 5;`
   - D) Tất cả đều được

2. Kiểu dữ liệu mặc định cho số thực là gì?
   - A) f32
   - B) f64
   - C) float
   - D) double

3. Shadowing cho phép:
   - A) Thay đổi giá trị biến bất biến
   - B) Khai báo lại biến với cùng tên
   - C) Thay đổi kiểu dữ liệu của biến
   - D) B và C đều đúng

**Đáp án:** 1-B, 2-B, 3-D

## Tổng kết

Trong bài học này, bạn đã học:
- ✅ Cách khai báo biến bất biến và khả biến
- ✅ Các kiểu dữ liệu cơ bản trong Rust
- ✅ Type inference và type annotation
- ✅ Shadowing và sự khác biệt với mutable
- ✅ Hằng số, tuple và array

## Bài học tiếp theo

Trong bài học tiếp theo, chúng ta sẽ tìm hiểu về:
- Hàm (Functions)
- Tham số và giá trị trả về
- Expressions vs Statements

---

**Tiếp tục học tập! 🚀**
