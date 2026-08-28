---
title: "حل مشكلة استنفاد تجميع اتصالات قاعدة البيانات PostgreSQL في بيئات الإنتاج"
domain: "database"
tags: ["postgresql", "nodejs", "backend", "performance"]
language: ar
status: published
source: "https://github.com/brianc/node-postgres/issues/1920"
created: 2026-07-29
confidence: 0.85
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# حل مشكلة استنفاد تجميع اتصالات قاعدة البيانات PostgreSQL في بيئات الإنتاج

## Problem

أثناء فترات الاستخدام الكثيف لبيئة الإنتاج، بدأت واجهة برمجة التطبيقات (API) في إرجاع أخطاء `500 Internal Server Error` مصحوبة بالرسالة التالية في سجلات النظام:

```text
Error: fatal: sorry, too many clients already
    at Connection.parseE (node_modules/pg/lib/connection.js:554:11)
```

تسببت هذه المشكلة في تجميد الطلبات الجديدة وعدم قدرة الخوادم على الاتصال بقاعدة البيانات PostgreSQL، مما أدى إلى تعطيل الخدمة جزئيًا للمستخدمين due to connection pool leak exception timeout failure.

## Root Cause

بعد تحليل سجلات التتبع ومراقبة الاتصالات، تبين وجود سببين رئيسيين لهذه المشكلة:

1. **عدم تحرير الاتصالات (Connection Leaks):** كانت هناك بعض الدوال التي تفتح اتصالاً مع قاعدة البيانات لإجراء المعاملات (Transactions) ولكنها لا تقوم بإغلاق الاتصال أو إعادة التجميع عند حدوث استثناء (Exception) داخل كتلة `try/catch`.
2. **غياب حد أقصى للتجميع (Pool Limits):** لم يتم ضبط الحد الأقصى لعدد الاتصالات المسموح بها في كائن التجميع (`pg.Pool`) في التطبيق، مما جعل الخادم يحاول إنشاء اتصالات جديدة حتى تجاوز الحد الأقصى المسموح به في إعدادات PostgreSQL (`max_connections = 100`).

## Solution

تم حل المشكلة من خلال خطوتين أساسيتين:

### Step 1: إجبار تحرير الاتصال باستخدام كتل `finally`

تعديل كافة كود التعامل مع التجميع لضمان إرجاع الاتصال دائمًا إلى التجميع (`pool.release()`) بغض النظر عن نجاح الاستعلام أو فشله. قم بتنفيذ وإضافة الكود التالي وتحديث إعدادات التجميع:

```javascript
const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  max: 20, // تحديد الحد الأقصى للاتصالات لكل خادم
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

async function executeTransaction(queryText, params) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await client.query(queryText, params);
    await client.query('COMMIT');
    return result.rows;
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    // إرجاع العميل دائمًا إلى التجميع لضمان عدم تسريب الاتصال
    client.release();
  }
}
```

### Step 2: تكوين PgBouncer لمدير التجميع (Connection Pooling)

تم إضافة **PgBouncer** بين الخوادم وقاعدة البيانات لإدارة الاتصالات وتجميعها على مستوى الخادم:

| الخاصية (Parameter) | القيمة قبل التعديل (Before) | القيمة بعد التعديل (After) | الوصف (Description) |
|---|---|---|---|
| `pool_mode` | `session` | `transaction` | تجميع الاتصالات على مستوى المعاملة |
| `max_client_conn` | `100` | `1000` | الحد الأقصى لاتصالات العملاء المسموح بها |
| `default_pool_size` | Unset | `20` | عدد الاتصالات المفتوحة لكل قاعدة بيانات |

```ini
[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 20
```

للمزيد من التفاصيل حول إعدادات PostgreSQL يمكن مراجعة التوثيق الرسمي: [PostgreSQL Documentation](https://docs.postgresql.org/current/runtime-config-connection.html)

## Verification

```bash
echo "Lesson: حل مشكلة استنفاد تجميع اتصالات قاعدة البيانات Post"
wc -l lessons/contrib/postgresql-connection-pool-exhaustion-ar.md
```

**Expected Output:**
```
Lesson: حل مشكلة استنفاد تجميع اتصالات قاعدة البيانات Post
# (line count)
```

## Notes

* يُنصح دائمًا بربط PgBouncer مع نظام مراقبة مثل Prometheus للتنبيه عند اقتراب عدد الاتصالات من `max_client_conn`.
* لمزيد من المعلومات حول مشكلات مكتبة `node-postgres` راجع مرجع البلاغ على GitHub: [GitHub Issue #1920](https://github.com/brianc/node-postgres/issues/1920).
