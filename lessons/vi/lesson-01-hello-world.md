---
title: "Bài 1: Hello World trong Rust"
language: vi
level: beginner
tags: [rust, basics, getting-started]
---

# Bài 1: Hello World trong Rust

## Giới thiệu

Chào mừng bạn đến với bài học đầu tiên về Rust! Trong bài này, chúng ta sẽ tìm hiểu cách viết chương trình "Hello World" đơn giản và hiểu về cấu trúc cơ bản của một chương trình Rust.

## Mục tiêu học tập

Sau khi hoàn thành bài học này, bạn sẽ có thể:
- Viết và chạy chương trình Rust đầu tiên
- Hiểu cấu trúc cơ bản của một chương trình Rust
- Sử dụng macro `println!` để in ra màn hình
- Biên dịch và chạy code Rust

## Chương trình Hello World

Hãy bắt đầu với chương trình Rust đơn giản nhất:

```rust
fn main() {
    println!("Hello, World!");
}
```

## Giải thích từng phần

### Hàm main

```rust
fn main() {
    // Code của bạn ở đây
}
```

- `fn` là từ khóa để khai báo một hàm (function)
- `main` là tên của hàm đặc biệt - đây là điểm bắt đầu của mọi chương trình Rust
- Dấu ngoặc nhọn `{}` bao quanh nội dung của hàm

### Macro println!

```rust
println!("Hello, World!");
```

- `println!` là một macro (chú ý dấu `!`) dùng để in text ra console
- Text được đặt trong dấu ngoặc kép `""`
- Dấu chấm phẩy `;` kết thúc câu lệnh

## Biên dịch và chạy

### Cách 1: Sử dụng rustc

```bash
# Biên dịch
rustc main.rs

# Chạy chương trình
./main
```

### Cách 2: Sử dụng Cargo (khuyến nghị)

```bash
# Tạo project mới
cargo new hello_world
cd hello_world

# Chạy chương trình
cargo run
```

## Bài tập thực hành

### Bài tập 1: In tên của bạn

Sửa chương trình để in ra tên của bạn:

```rust
fn main() {
    println!("Xin chào, tôi là [Tên của bạn]!");
}
```

### Bài tập 2: In nhiều dòng

Viết chương trình in ra nhiều dòng text:

```rust
fn main() {
    println!("Dòng thứ nhất");
    println!("Dòng thứ hai");
    println!("Dòng thứ ba");
}
```

### Bài tập 3: Sử dụng biến

Tạo biến và in giá trị của nó:

```rust
fn main() {
    let name = "Rust";
    println!("Xin chào, {}!", name);
}
```

## Khái niệm quan trọng

### Comments (Chú thích)

Rust hỗ trợ hai loại comment:

```rust
fn main() {
    // Đây là comment một dòng
    
    /* Đây là comment
       nhiều dòng */
    
    println!("Hello, World!");
}
```

### Format String

Bạn có thể chèn giá trị vào string:

```rust
fn main() {
    let x = 5;
    let y = 10;
    println!("x = {} và y = {}", x, y);
}
```

## Lỗi thường gặp

### 1. Quên dấu chấm phẩy

```rust
// SAI
println!("Hello")

// ĐÚNG
println!("Hello");
```

### 2. Quên dấu ! trong macro

```rust
// SAI
println("Hello");

// ĐÚNG
println!("Hello");
```

### 3. Sai tên hàm main

```rust
// SAI
fn Main() {
    println!("Hello");
}

// ĐÚNG
fn main() {
    println!("Hello");
}
```

## Kiểm tra kiến thức

1. Hàm nào là điểm bắt đầu của chương trình Rust?
   - A) start()
   - B) main()
   - C) begin()
   - D) init()

2. Dấu nào cho biết `println` là một macro?
   - A) @
   - B) #
   - C) !
   - D) $

3. Câu lệnh nào sau đây là đúng?
   - A) `println("Hello");`
   - B) `println!("Hello")`
   - C) `println!("Hello");`
   - D) `print!("Hello");`

**Đáp án:** 1-B, 2-C, 3-C

## Tổng kết

Trong bài học này, bạn đã học:
- ✅ Cấu trúc cơ bản của chương trình Rust
- ✅ Cách sử dụng hàm `main()`
- ✅ Cách in text ra console với `println!`
- ✅ Cách biên dịch và chạy code Rust
- ✅ Các lỗi thường gặp và cách tránh

## Bài học tiếp theo

Trong bài học tiếp theo, chúng ta sẽ tìm hiểu về:
- Biến và kiểu dữ liệu trong Rust
- Tính bất biến (immutability)
- Shadowing và mutability

## Tài liệu tham khảo

- [The Rust Programming Language Book](https://doc.rust-lang.org/book/)
- [Rust by Example](https://doc.rust-lang.org/rust-by-example/)
- [Rust Documentation](https://doc.rust-lang.org/)

---

**Chúc mừng bạn đã hoàn thành bài học đầu tiên! 🎉**
