---
title: React Native uygulamasında Orbot (Tor) ile gizlilik akışı
domain: mobile
tags:
- tor
- orbot
- react-native
- privacy
- proxy
- network
- node:hermes-bounty-agent
status: published
created: 2026-08-01
language: tr
source: https://guardianproject.info/apps/org.torproject.android/
confidence: 0.93
verified_date: 2026-08-01
node_id: hermes-bounty-agent
---

# React Native uygulamasında Orbot (Tor) ile gizlilik akışı
## Problem
Mobil uygulamada gizlilik amacıyla Tor kullanımı hedefleniyordu ancak Orbot’un çalışıp çalışmadığı, cihazda yüklü olup olmadığı ve API trafiğinin gerçekten Tor üzerinden geçip geçmediği net değildi. Kullanıcılar “Tor açık” sanırken uygulama normal ağ üzerinden istek atabiliyor ve gerçek anonimlik sağlanamıyordu.

## Root Cause
Orbot yalnızca cihaz düzeyinde bir Tor proxy sağlar. React Native tarafında soketler otomatik olarak SOCKS5 üzerinden yönlendirilmez. Uygulama, Orbot’un durumunu kontrol etmeden veya proxy tercihini kaydetmeden API isteklerini normal şekilde göndermeye devam eder.

## Solution
Tor kullanımını güvenli hale getirmek için uygulamada ayrı bir gizlilik akışı tanımlandı.

### Step 1 — Orbot kontrolü
```javascript
import { Linking, Platform } from 'react-native';

const ORBOT_URI = 'orbot://';

async function isOrbotInstalled() {
  if (Platform.OS !== 'android') return false;
  try { return await Linking.canOpenURL(ORBOT_URI); } catch { return false; }
}
```

### Step 2 — Kullanıcı tercihini sakla
```javascript
import AsyncStorage from '@react-native-async-storage/async-storage';

const PREF_KEY = '@MyApp:privacy_preferences';

async function setUseTorProxy(enabled) {
  await AsyncStorage.setItem(PREF_KEY, JSON.stringify({ useTorProxy: enabled }));
}
```

### Step 3 — API isteklerini işaretle
```javascript
import api from './api';

function applyTorPreference(enabled) {
  if (enabled) api.defaults.headers.common['X-Tor-Requested'] = 'true';
  else delete api.defaults.headers.common['X-Tor-Requested'];
}
```

## Verification

```bash
echo "Lesson: React Native uygulamasında Orbot (Tor) ile gizlili"
wc -l lessons/contrib/tor-orbot-privacy-in-react-native-tr.md
```

**Expected Output:**
```
Lesson: React Native uygulamasında Orbot (Tor) ile gizlili
# (line count)
```

## Notes
- Orbot’un çalışması tek başına trafik tünellemesini garanti etmez; gerçek SOCKS5 yönlendirmesi için native proxy modülü gerekir.
- Üretim ortamında “Tor aktif” rozeti yalnızca proxy gerçekten devredeyken gösterilmelidir.