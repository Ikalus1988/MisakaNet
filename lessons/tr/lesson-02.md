---
title: "Struct'lar, Enum'lar ve Pattern Matching"
language: tr
level: intermediate
tags: [rust, structs, enums, pattern-matching]
---

# Struct'lar, Enum'lar ve Pattern Matching

Bu derste Rust'ın güçlü veri yapılarını ve pattern matching özelliğini öğreneceğiz.

## Struct'lar (Yapılar)

Struct'lar ilişkili verileri gruplamak için kullanılır.

### Temel Struct Tanımlama

```rust
struct Kullanıcı {
    kullanıcı_adı: String,
    email: String,
    yaş: u32,
    aktif: bool,
}

fn main() {
    let kullanıcı1 = Kullanıcı {
        kullanıcı_adı: String::from("ahmet123"),
        email: String::from("ahmet@example.com"),
        yaş: 25,
        aktif: true,
    };
    
    println!("Kullanıcı: {}, Email: {}", 
             kullanıcı1.kullanıcı_adı, 
             kullanıcı1.email);
}
```

### Değiştirilebilir Struct'lar

```rust
fn main() {
    let mut kullanıcı = Kullanıcı {
        kullanıcı_adı: String::from("mehmet456"),
        email: String::from("mehmet@example.com"),
        yaş: 30,
        aktif: true,
    };
    
    kullanıcı.email = String::from("yeni_email@example.com");
    println!("Yeni email: {}", kullanıcı.email);
}
```

### Struct Metodları

```rust
struct Dikdörtgen {
    genişlik: u32,
    yükseklik: u32,
}

impl Dikdörtgen {
    // Metod
    fn alan(&self) -> u32 {
        self.genişlik * self.yükseklik
    }
    
    fn çevre(&self) -> u32 {
        2 * (self.genişlik + self.yükseklik)
    }
    
    // İlişkili fonksiyon (constructor)
    fn kare(boyut: u32) -> Dikdörtgen {
        Dikdörtgen {
            genişlik: boyut,
            yükseklik: boyut,
        }
    }
    
    fn sığar_mı(&self, diğer: &Dikdörtgen) -> bool {
        self.genişlik > diğer.genişlik && self.yükseklik > diğer.yükseklik
    }
}

fn main() {
    let dikdörtgen = Dikdörtgen {
        genişlik: 30,
        yükseklik: 50,
    };
    
    println!("Alan: {}", dikdörtgen.alan());
    println!("Çevre: {}", dikdörtgen.çevre());
    
    let kare = Dikdörtgen::kare(20);
    println!("Kare alanı: {}", kare.alan());
    
    if dikdörtgen.sığar_mı(&kare) {
        println!("Kare dikdörtgenin içine sığar");
    }
}
```

## Enum'lar (Numaralandırmalar)

Enum'lar bir değerin birkaç olası varyanttan biri olabileceğini tanımlar.

### Temel Enum

```rust
enum IpAdresiTürü {
    V4,
    V6,
}

fn main() {
    let dört = IpAdresiTürü::V4;
    let altı = IpAdresiTürü::V6;
    
    yönlendir(dört);
    yönlendir(altı);
}

fn yönlendir(ip_türü: IpAdresiTürü) {
    // İşlem yap
}
```

### Veri İçeren Enum'lar

```rust
enum IpAdresi {
    V4(u8, u8, u8, u8),
    V6(String),
}

fn main() {
    let ev = IpAdresi::V4(127, 0, 0, 1);
    let döngü = IpAdresi::V6(String::from("::1"));
}
```

### Karmaşık Enum Örneği

```rust
enum Mesaj {
    Çık,
    Taşı { x: i32, y: i32 },
    Yaz(String),
    RenkDeğiştir(i32, i32, i32),
}

impl Mesaj {
    fn çağır(&self) {
        match self {
            Mesaj::Çık => println!("Çıkılıyor..."),
            Mesaj::Taşı { x, y } => println!("({}, {}) konumuna taşınıyor", x, y),
            Mesaj::Yaz(metin) => println!("Mesaj: {}", metin),
            Mesaj::RenkDeğiştir(r, g, b) => {
                println!("Renk RGB({}, {}, {}) olarak değiştiriliyor", r, g, b)
            }
        }
    }
}

fn main() {
    let mesajlar = vec![
        Mesaj::Yaz(String::from("Merhaba")),
        Mesaj::Taşı { x: 10, y: 20 },
        Mesaj::RenkDeğiştir(255, 0, 0),
        Mesaj::Çık,
    ];
    
    for mesaj in mesajlar {
        mesaj.çağır();
    }
}
```

## Option Enum'u

Rust'ta null yoktur. Bunun yerine `Option<T>` enum'u kullanılır:

```rust
fn bölme(bölünen: f64, bölen: f64) -> Option<f64> {
    if bölen == 0.0 {
        None
    } else {
        Some(bölünen / bölen)
    }
}

fn main() {
    let sonuç1 = bölme(10.0, 2.0);
    let sonuç2 = bölme(10.0, 0.0);
    
    match sonuç1 {
        Some(değer) => println!("Sonuç: {}", değer),
        None => println!("Bölme yapılamadı"),
    }
    
    match sonuç2 {
        Some(değer) => println!("Sonuç: {}", değer),
        None => println!("Sıfıra bölme hatası!"),
    }
    
    // unwrap_or ile varsayılan değer
    let güvenli_sonuç = sonuç2.unwrap_or(0.0);
    println!("Güvenli sonuç: {}", güvenli_sonuç);
}
```

## Pattern Matching

Pattern matching Rust'ın en güçlü özelliklerinden biridir.

### Temel Match

```rust
enum Madeni {
    Kuruş,
    Beşlik,
    Onluk,
    Çeyrek,
}

fn değer_kuruş(madeni: Madeni) -> u8 {
    match madeni {
        Madeni::Kuruş => 1,
        Madeni::Beşlik => 5,
        Madeni::Onluk => 10,
        Madeni::Çeyrek => 25,
    }
}

fn main() {
    let madeni = Madeni::Çeyrek;
    println!("Değer: {} kuruş", değer_kuruş(madeni));
}
```

### Option ile Match

```rust
fn artı_bir(x: Option<i32>) -> Option<i32> {
    match x {
        None => None,
        Some(i) => Some(i + 1),
    }
}

fn main() {
    let beş = Some(5);
    let altı = artı_bir(beş);
    let hiç = artı_bir(None);
    
    println!("beş: {:?}, altı: {:?}, hiç: {:?}", beş, altı, hiç);
}
```

### if let - Kısa Sözdizimi

```rust
fn main() {
    let bazı_değer = Some(3);
    
    // Uzun yol
    match bazı_değer {
        Some(3) => println!("üç"),
        _ => (),
    }
    
    // Kısa yol
    if let Some(3) = bazı_değer {
        println!("üç");
    }
    
    // else ile
    let madeni = Madeni::Çeyrek;
    let mut sayaç = 0;
    
    if let Madeni::Çeyrek = madeni {
        println!("Çeyrek bulundu!");
    } else {
        sayaç += 1;
    }
}
```

## Result Enum'u - Hata Yönetimi

```rust
use std::fs::File;
use std::io::ErrorKind;

fn dosya_aç(dosya_adı: &str) -> Result<File, String> {
    match File::open(dosya_adı) {
        Ok(dosya) => Ok(dosya),
        Err(hata) => match hata.kind() {
            ErrorKind::NotFound => Err(String::from("Dosya bulunamadı")),
            ErrorKind::PermissionDenied => Err(String::from("İzin reddedildi")),
            _ => Err(String::from("Bilinmeyen hata")),
        },
    }
}

fn main() {
    match dosya_aç("test.txt") {
        Ok(_) => println!("Dosya başarıyla açıldı"),
        Err(hata) => println!("Hata: {}", hata),
    }
}
```

## Pratik Örnek: Sipariş Sistemi

```rust
#[derive(Debug)]
enum SiparişDurumu {
    Beklemede,
    İşleniyor,
    Kargoda { takip_no: String },
    Teslim edildi,
    İptal { sebep: String },
}

#[derive(Debug)]
struct Sipariş {
    id: u32,
    ürün: String,
    miktar: u32,
    durum: SiparişDurumu,
}

impl Sipariş {
    fn yeni(id: u32, ürün: String, miktar: u32) -> Sipariş {
        Sipariş {
            id,
            ürün,
            miktar,
            durum: SiparişDurumu::Beklemede,
        }
    }
    
    fn durum_güncelle(&mut self, yeni_durum: SiparişDurumu) {
        self.durum = yeni_durum;
    }
    
    fn durum_mesajı(&self) -> String {
        match &self.durum {
            SiparişDurumu::Beklemede => {
                format!("Sipariş #{} beklemede", self.id)
            }
            SiparişDurumu::İşleniyor => {
                format!("Sipariş #{} işleniyor", self.id)
            }
            SiparişDurumu::Kargoda { takip_no } => {
                format!("Sipariş #{} kargoda. Takip no: {}", self.id, takip_no)
            }
            SiparişDurumu::Teslim edildi => {
                format!("Sipariş #{} teslim edildi", self.id)
            }
            SiparişDurumu::İptal { sebep } => {
                format!("Sipariş #{} iptal edildi. Sebep: {}", self.id, sebep)
            }
        }
    }
}

fn main() {
    let mut sipariş = Sipariş::yeni(
        1001,
        String::from("Laptop"),
        1
    );
    
    println!("{}", sipariş.durum_mesajı());
    
    sipariş.durum_güncelle(SiparişDurumu::İşleniyor);
    println!("{}", sipariş.durum_mesajı());
    
    sipariş.durum_güncelle(SiparişDurumu::Kargoda {
        takip_no: String::from("TR123456789"),
    });
    println!("{}", sipariş.durum_mesajı());
    
    sipariş.durum_güncelle(SiparişDurumu::Teslim edildi);
    println!("{}", sipariş.durum_mesajı());
}
```

## Özet

Bu derste öğrendiklerimiz:

- ✅ Struct tanımlama ve kullanma
- ✅ Struct metodları ve ilişkili fonksiyonlar
- ✅ Enum'lar ve varyantlar
- ✅ Option ve Result enum'ları
- ✅ Pattern matching ile match ve if let
- ✅ Gerçek dünya örneği: Sipariş sistemi

Rust yolculuğunuz devam ediyor! 🦀
