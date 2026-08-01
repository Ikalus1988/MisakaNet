---
title: Pengenalan Pemrograman
language: id
---

# Pengenalan Pemrograman

Selamat datang di pelajaran pertama tentang pemrograman! Dalam pelajaran ini, kita akan mempelajari konsep-konsep dasar yang akan membantu Anda memulai perjalanan sebagai programmer.

## Apa itu Pemrograman?

Pemrograman adalah proses menulis instruksi yang dapat dijalankan oleh komputer untuk menyelesaikan tugas tertentu. Instruksi-instruksi ini ditulis dalam bahasa pemrograman yang dapat dipahami oleh komputer.

## Konsep Dasar

### 1. Variabel

Variabel adalah tempat penyimpanan data dalam program. Bayangkan variabel seperti kotak yang dapat menyimpan nilai.

```javascript
let nama = "Budi";
let umur = 25;
let tinggi = 170.5;
```

### 2. Tipe Data

Tipe data menentukan jenis nilai yang dapat disimpan dalam variabel:

- **String**: Teks atau karakter (contoh: "Halo Dunia")
- **Number**: Angka (contoh: 42, 3.14)
- **Boolean**: Nilai benar atau salah (true/false)
- **Array**: Kumpulan nilai (contoh: [1, 2, 3])

```javascript
let pesan = "Halo Dunia";  // String
let jumlah = 100;          // Number
let aktif = true;          // Boolean
let angka = [1, 2, 3, 4];  // Array
```

### 3. Operator

Operator digunakan untuk melakukan operasi pada variabel dan nilai:

```javascript
// Operator Aritmatika
let hasil = 10 + 5;     // Penjumlahan: 15
let kurang = 10 - 5;    // Pengurangan: 5
let kali = 10 * 5;      // Perkalian: 50
let bagi = 10 / 5;      // Pembagian: 2

// Operator Perbandingan
let sama = (5 == 5);           // true
let lebihBesar = (10 > 5);     // true
let lebihKecil = (3 < 8);      // true
```

### 4. Kondisi (If-Else)

Kondisi memungkinkan program membuat keputusan berdasarkan situasi tertentu:

```javascript
let nilai = 85;

if (nilai >= 80) {
    console.log("Nilai Anda: A");
} else if (nilai >= 70) {
    console.log("Nilai Anda: B");
} else {
    console.log("Nilai Anda: C");
}
```

### 5. Perulangan (Loop)

Perulangan memungkinkan kita menjalankan kode yang sama berulang kali:

```javascript
// For Loop
for (let i = 1; i <= 5; i++) {
    console.log("Iterasi ke-" + i);
}

// While Loop
let hitungan = 0;
while (hitungan < 3) {
    console.log("Hitungan: " + hitungan);
    hitungan++;
}
```

### 6. Fungsi

Fungsi adalah blok kode yang dapat digunakan kembali untuk melakukan tugas tertentu:

```javascript
function sapa(nama) {
    return "Halo, " + nama + "!";
}

let pesan = sapa("Ani");
console.log(pesan);  // Output: Halo, Ani!

// Fungsi dengan beberapa parameter
function tambah(a, b) {
    return a + b;
}

let jumlah = tambah(5, 3);
console.log(jumlah);  // Output: 8
```

## Latihan Praktis

Mari kita buat program sederhana yang menggabungkan konsep-konsep di atas:

```javascript
// Program Kalkulator Sederhana
function kalkulator(angka1, angka2, operasi) {
    if (operasi === "tambah") {
        return angka1 + angka2;
    } else if (operasi === "kurang") {
        return angka1 - angka2;
    } else if (operasi === "kali") {
        return angka1 * angka2;
    } else if (operasi === "bagi") {
        if (angka2 !== 0) {
            return angka1 / angka2;
        } else {
            return "Error: Tidak bisa membagi dengan nol";
        }
    } else {
        return "Operasi tidak valid";
    }
}

// Menggunakan kalkulator
console.log(kalkulator(10, 5, "tambah"));  // 15
console.log(kalkulator(10, 5, "kurang"));  // 5
console.log(kalkulator(10, 5, "kali"));    // 50
console.log(kalkulator(10, 5, "bagi"));    // 2
```

## Tips untuk Pemula

1. **Praktik Teratur**: Kunci untuk menjadi programmer yang baik adalah latihan konsisten.
2. **Mulai dari yang Kecil**: Jangan langsung mencoba membuat program yang rumit. Mulailah dengan program sederhana.
3. **Baca Error Messages**: Pesan error adalah teman Anda. Mereka memberi tahu Anda apa yang salah.
4. **Komentar Kode Anda**: Tulis komentar untuk menjelaskan apa yang dilakukan kode Anda.
5. **Debugging**: Belajar menggunakan console.log() untuk memeriksa nilai variabel.

```javascript
// Contoh penggunaan komentar
let harga = 50000;  // Harga dalam Rupiah
let diskon = 0.1;   // Diskon 10%

// Menghitung harga setelah diskon
let hargaAkhir = harga - (harga * diskon);
console.log("Harga akhir: Rp" + hargaAkhir);
```

## Kesimpulan

Dalam pelajaran ini, Anda telah mempelajari:

- Apa itu pemrograman
- Variabel dan tipe data
- Operator dasar
- Struktur kontrol (if-else)
- Perulangan (loop)
- Fungsi

Konsep-konsep ini adalah fondasi dari hampir semua bahasa pemrograman. Setelah Anda menguasai dasar-dasar ini, Anda akan lebih mudah mempelajari konsep yang lebih advanced.

## Latihan Mandiri

Coba buat program sederhana berikut:

1. Program yang memeriksa apakah sebuah angka genap atau ganjil
2. Program yang menghitung faktorial dari sebuah angka
3. Program yang mencetak tabel perkalian dari 1 sampai 10

Selamat belajar dan terus berlatih! 🚀
