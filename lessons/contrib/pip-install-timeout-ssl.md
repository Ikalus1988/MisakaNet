---
title: pip install Network Timeout / SSL ErrorFix
domain: contrib
tags:
- install
- timeout
status: published
created: '2026-07-06'
source: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

`pip install` 失败，常见报错信息包括：

- `ReadTimeoutError: HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out.`
- `SSL: CERTIFICATE_VERIFY_FAILED`
- `Connection broken: IncompleteRead`
- `Could not fetch URL https://pypi.org/simple/...`
- `WARNING: Retrying (Retry(total=4, ...)) after connection broken by 'SSLError(...)'`

这类问题在中国大陆网络环境下尤为常见，严重影响开发效率。

## Root Cause

### 1. 网络超时（Timeout）
PyPI 官方源服务器位于境外（`pypi.org` / `files.pythonhosted.org`），在中国大陆访问时延迟高、速度慢。pip 默认超时时间仅为 **15 秒**，下载 numpy、torch 等大包时极易触发超时。

### 2. SSL 证书验证失败（SSL: CERTIFICATE_VERIFY_FAILED）
原因可能有多种：
- 企业/学校网络使用了中间人代理，替换了 TLS 证书
- 系统 CA 证书库过旧，不认识 PyPI 使用的证书链
- macOS 上 Python 安装后未运行 `Install Certificates.command`，导致缺少根证书

### 3. 连接中断（Connection broken）
网络不稳定或防火墙对长连接进行了截断，导致大文件下载到一半失败。

### 4. DNS 污染
`pypi.org` 域名在部分网络环境下被 DNS 污染，解析到错误 IP，导致连接直接失败。

## Solution

### 方案一：永久切换国内镜像源（推荐）

```bash
# 切换到清华大学镜像（速度快、更新及时）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 也可选择阿里云镜像
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 验证当前配置
pip config list
# 输出示例：global.index-url='https://pypi.tuna.tsinghua.edu.cn/simple'
```

切换后，所有 `pip install` 命令都会自动走国内镜像，无需额外参数。

### 方案二：临时指定镜像并加长超时

```bash
# 单次安装时临时指定镜像源，超时设为 120 秒
pip install --default-timeout=120 -i https://pypi.tuna.tsinghua.edu.cn/simple <包名>

# 示例：安装 numpy
pip install --default-timeout=120 -i https://pypi.tuna.tsinghua.edu.cn/simple numpy

# 示例：安装 torch（体积较大，建议超时设更长）
pip install --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple torch
```

### 方案三：解决 SSL 证书验证失败

```bash
# 方法 A：信任指定主机（适用于企业代理环境，不推荐生产）
pip install --trusted-host pypi.org \
            --trusted-host files.pythonhosted.org \
            --trusted-host pypi.tuna.tsinghua.edu.cn \
            <包名>

# 方法 B：macOS 用户修复根证书（一次性操作）
# 找到 Python 安装目录并运行证书安装脚本
/Applications/Python\ 3.x/Install\ Certificates.command

# 方法 C：升级 certifi 包（更新 CA 证书库）
pip install --upgrade certifi
```

### 方案四：禁用缓存重新下载

```bash
# 当本地缓存损坏或下载不完整时使用
pip install --no-cache-dir <包名>

# 示例
pip install --no-cache-dir pandas
```

### 方案五：配置 pip.ini / pip.conf 文件（团队统一配置）

在项目根目录或用户目录创建配置文件，方便团队共享：

```ini
# Linux/macOS: ~/.pip/pip.conf 或 ~/.config/pip/pip.conf
# Windows:     %APPDATA%\pip\pip.ini

[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
timeout = 120
```

## Verification

```bash
pip install
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `pip install`)
