---
title: "Rust'a Giriş: Temel Kavramlar"
language: tr
level: beginner
tags: [rust, basics, variables, types]
---

# Rust'a Giriş: Temel Kavramlar

Rust, güvenli, hızlı ve eşzamanlı sistemler geliştirmek için tasarlanmış modern bir programlama dilidir. Bu derste Rust'ın temel kavramlarını öğreneceğiz.

## Değişkenler ve Değişmezlik

Rust'ta değişkenler varsayılan olarak değişmezdir (immutable). Bu, bir değer atandıktan sonra değiştirilemeyeceği anlamına gelir.

```rust
fn main() {
    let x = 5;
    println!("x'in değeri: {}", x);
    
    // x = 6; // Bu hata verir!
}
```

Değişken bir değişken oluşturmak için `mut` anahtar kelimesini kullanırız:

```rust
fn main() {
    let mut y = 5;
    println!("y'nin değeri: {}", y);
    
    y = 6;
    println!("y'nin yeni değeri: {}", y);
}
```

## Veri Tipleri

Rust statik olarak yazılmış bir dildir. Temel veri tipleri:

### Tamsayılar

```rust
fn main() {
    let a: i32 = 42;        // 32-bit işaretli tamsayı
    let b: u64 = 100;       // 64-bit işaretsiz tamsayı
    let c = 10;             // Varsayılan: i32
    
    println!("a: {}, b: {}, c: {}", a, b, c);
}
```

### Ondalık Sayılar

```rust
fn main() {
    let x: f64 = 3.14;      // 64-bit ondalık
    let y: f32 = 2.5;       // 32-bit ondalık
    
    println!("x: {}, y: {}", x, y);
}
```

### Boolean ve Karakter

```rust
fn main() {
    let doğru: bool = true;
    let yanlış: bool = false;
    let harf: char = 'A';
    let emoji: char = '😊';
    
    println!("Boolean: {}, {}", doğru, yanlış);
    println!("Karakterler: {}, {}", harf, emoji);
}
```

## Fonksiyonlar

Rust'ta fonksiyonlar `fn` anahtar kelimesi ile tanımlanır:

```rust
fn selamla(isim: &str) {
    println!("Merhaba, {}!", isim);
}

fn topla(a: i32, b: i32) -> i32 {
    a + b  // Return ifadesi noktalı virgül olmadan
}

fn main() {
    selamla("Ahmet");
    
    let sonuç = topla(5, 7);
    println!("Toplam: {}", sonuç);
}
```

## Kontrol Akışı

### If İfadeleri

```rust
fn main() {
    let sayı = 7;
    
    if sayı < 5 {
        println!("Sayı 5'ten küçük");
    } else if sayı == 5 {
        println!("Sayı 5'e eşit");
    } else {
        println!("Sayı 5'ten büyük");
    }
    
    // If bir ifadedir, değer döndürebilir
    let sonuç = if sayı % 2 == 0 { "çift" } else { "tek" };
    println!("Sayı {}", sonuç);
}
```

### Döngüler

```rust
fn main() {
    // loop - sonsuz döngü
    let mut sayaç = 0;
    loop {
        sayaç += 1;
        if sayaç == 5 {
            break;
        }
    }
    println!("Sayaç: {}", sayaç);
    
    // while döngüsü
    let mut n = 3;
    while n > 0 {
        println!("{}!", n);
        n -= 1;
    }
    println!("Başla!");
    
    // for döngüsü
    for i in 1..=5 {
        println!("i: {}", i);
    }
    
    // Dizi üzerinde döngü
    let dizı = [10, 20, 30, 40, 50];
    for eleman in dizı.iter() {
        println!("Değer: {}", eleman);
    }
}
```

## Sahiplik (Ownership) - Rust'ın Süper Gücü

Rust'ın en önemli özelliği sahiplik sistemidir. Bu sistem bellek güvenliğini çöp toplayıcı olmadan sağlar.

### Temel Kurallar

1. Her değerin bir sahibi vardır
2. Aynı anda sadece bir sahip olabilir
3. Sahip kapsam dışına çıktığında değer temizlenir

```rust
fn main() {
    let s1 = String::from("merhaba");
    let s2 = s1;  // s1'in sahipliği s2'ye taşındı
    
    // println!("{}", s1); // Hata! s1 artık geçerli değil
    println!("{}", s2);   // Bu çalışır
    
    // Klonlama ile kopyalama
    let s3 = s2.clone();
    println!("s2: {}, s3: {}", s2, s3);
}
```

### Referanslar ve Ödünç Alma

```rust
fn uzunluk_hesapla(s: &String) -> usize {
    s.len()
}

fn main() {
    let metin = String::from("Merhaba Dünya");
    let uzunluk = uzunluk_hesapla(&metin);
    
    println!("'{}' metninin uzunluğu: {}", metin, uzunluk);
}
```

## Alıştırmalar

### Alıştırma 1: Sıcaklık Dönüştürücü

Celsius'u Fahrenheit'a çeviren bir fonksiyon yazın:

```rust
fn celsius_to_fahrenheit(celsius: f64) -> f64 {
    celsius * 9.0 / 5.0 + 32.0
}

fn main() {
    let celsius = 25.0;
    let fahrenheit = celsius_to_fahrenheit(celsius);
    println!("{}°C = {}°F", celsius, fahrenheit);
}
```

### Alıştırma 2: Fibonacci Sayıları

N'inci Fibonacci sayısını hesaplayan bir fonksiyon yazın:

```rust
fn fibonacci(n: u32) -> u32 {
    if n <= 1 {
        return n;
    }
    
    let mut a = 0;
    let mut b = 1;
    
    for _ in 2..=n {
        let temp = a + b;
        a = b;
        b = temp;
    }
    
    b
}

fn main() {
    for i in 0..10 {
        println!("fibonacci({}) = {}", i, fibonacci(i));
    }
}
```

### Alıştırma 3: Kelime Sayacı

Bir metindeki kelime sayısını bulan bir fonksiyon yazın:

```rust
fn kelime_say(metin: &str) -> usize {
    metin.split_whitespace().count()
}

fn main() {
    let cümle = "Rust öğrenmek çok eğlenceli";
    let sayı = kelime_say(cümle);
    println!("'{}' cümlesinde {} kelime var", cümle, sayı);
}
```

## Özet

Bu derste öğrendiklerimiz:

- ✅ Değişkenler ve değişmezlik
- ✅ Temel veri tipleri (tamsayılar, ondalık sayılar, boolean, karakter)
- ✅ Fonksiyon tanımlama ve kullanma
- ✅ Kontrol akışı (if, loop, while, for)
- ✅ Sahiplik sistemi ve referanslar
- ✅ Pratik alıştırmalar

## Sonraki Adımlar

Rust yolculuğunuza devam etmek için:

1. Struct'lar ve Enum'lar
2. Pattern Matching
3. Error Handling
4. Modüller ve Paketler
5. Trait'ler ve Generics

Kodlamaya devam edin! 🦀
