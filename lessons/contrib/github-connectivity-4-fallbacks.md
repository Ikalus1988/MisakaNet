---
{
  "domain": "devops",
  "title": "GitHub Connectivity — 4 Fallbacks (从最常踩的坑到最激进方案)",
  "verification": "metadata-normalized",
  "tags": [
    "git",
    "github",
    "network",
    "WSL",
    "GFW",
    "fallback",
    "connectivity",
    "DNS",
    "proxy",
    "hosts"
  ],
  "status": "published",
  "confidence": "0.92",
  "created": "2026-08-01",
  "updated": "2026-08-01",
  "source": "Real incident: 克莱恩 22:38 GMT+8 反馈「撞墙问题有几种方案」+ 自查发现 root cause = Agent-Medici 仓 local .git/config 死代理（不是 hosts）",
  "related_lessons": [
    "lessons/contrib/github-dns-443-block-hosts-workaround.md",
    "lessons/contrib/git-push-without-shell-agent.md",
    "lessons/contrib/lesson-08-pip-https-proxy-clash.md"
  ],
  "evidence_level": "E3",
  "summary_plain": "git 操作卡住但裸 curl 能通，多半是仓库本地 .git/config 里的死代理；按代理→alias→hosts→直连四级排查。",
  "trigger": "git push/clone/ls-remote 卡 124 timeout，但 curl https://github.com 返回 200",
  "verify": "git config --local --list | grep -i proxy 打出 proxy 行即命中 Fallback 1；unset 后 git ls-remote 拿到 commit SHA 且 exit 0 即修复。"
}
---

# GitHub Connectivity — 4 Fallbacks

> 4 个方案**按推荐度排序**,前 3 个不动 sudo,第 4 个最激进。
> **关键:撞墙时先 smoke 全栈再下结论**(见底部"诊断 SOP")。

## Fallback 1: 清 `.git/config` 死代理(**最常踩的坑**)

### 症状

- `git push` / `git clone` / `git ls-remote` 卡 124(timeout)
- 裸 `curl https://github.com` 反而 HTTP 200 通
- 这**不是 github.com 撞墙**,是 git 走的是个死的 Clash 代理

### 根因

某个废弃仓的 local `.git/config` 配了 `http.proxy=socks5://172.19.128.1:7890`(Windows Clash,已死链)。
WSL 没自动继承,所以别的仓不受影响——**只有这个仓的 git 操作撞墙**。

### 真实案例(2026-08-01)

`Agent-Medici`(已废弃,被 MisakaNet 取代)仓的 `.git/config`:

```ini
[remote "origin"]
    url = https://github.com/Ikalus1988/Agent-Medici
[http]
    proxy = socks5://172.19.128.1:7890   ← 这条是死的
```

### 诊断

```bash
# 看当前仓 git 操作走没走代理
GIT_CURL_VERBOSE=1 git ls-remote https://github.com/<org>/<repo>.git HEAD 2>&1 | head -5
# 输出 "Trying 172.19.128.1:7890..." 就是撞死代理
```

### 修复

```bash
# 1. 检查
git config --local --list | grep -i proxy

# 2. 清掉(只清 http.proxy / https.proxy,别乱 unset 其他)
git config --local --unset http.proxy
git config --local --unset https.proxy

# 3. 全局也清(保险)
git config --global --unset http.proxy
git config --global --unset https.proxy

# 4. 验证(cd 到别的目录,因为本仓还有可能 cache)
cd /tmp
git ls-remote https://github.com/<org>/<repo>.git HEAD
# 期望:拿到 commit SHA,exit 0
```

## Fallback 2: git alias `ghub` 强制 IP 解析(**无 sudo,常驻方案**)

### 适用

- Fallback 1 清完代理,`git ls-remote` 还是 timeout
- 或者**想预防性**给所有 git 操作加备用 IP
- WSL 没 sudo 不能改 hosts

### 原理

`http.curloptResolve` 是 git 的 libcurl 选项,等价于 `curl --resolve`,在 libcurl 层强制域名解析,绕过系统 hosts 和 DNS。

### 落地

```bash
# 加 alias 到 ~/.gitconfig
git config --global alias.ghub '!f() {
  git -c "http.curloptResolve=github.com:443:140.82.112.3" "$@"
}; f'

# 验证
cd /tmp
git ghub ls-remote https://github.com/Ikalus1988/MisakaNet.git HEAD
# 期望:拿到 commit SHA
```

### 用法

```bash
# 日常 git 命令全部加 ghub 前缀
git ghub push origin main
git ghub clone https://github.com/org/repo.git
git ghub fetch
git ghub ls-remote origin HEAD
```

## Fallback 3: `/etc/hosts` 备用 IP(**有 sudo,常驻方案**)

> 完整内容见 `lessons/contrib/github-dns-443-block-hosts-workaround.md`

### 关键陷阱

- **只加 `github.com`,别加 `api.github.com`**(IP 段不同,加了 API 会 301)
- WSL 默认没 sudo,会 Permission denied
- hosts 修改即时生效,无需重启

```bash
# 扫可达 IP
~/bin/ping_github.sh

# 写 hosts(假设 140.82.112.3 可达)
echo "140.82.112.3  github.com" | sudo tee -a /etc/hosts
```

## Fallback 4: 真实 IP + Host 头直连(**最激进,只用于 fetch/clone/push**)

> 完整内容见 `lessons/contrib/git-push-without-shell-agent.md` 末段

### 适用

- 上面 3 个全失败,gpush 卡 GnuTLS -110
- **接受关 SSL 验证的安全风险**(有 MITM 风险,token 可能泄漏)
- 只对 fetch/clone/push 用,**别用这个访问 GitHub Web**

```bash
git -c "http.extraHeader=Host: github.com" \
    -c http.sslVerify=false \
    push "https://<token>@20.205.243.166/<org>/<repo>.git" main
```

## 诊断 SOP(撞墙时必走)

**别看 smoke 通过就以为撞墙修了。每次撞墙按这个顺序查:**

1. **本地代理状态**
   ```bash
   git config --local --list | grep -i proxy   # 看本仓
   git config --global --list | grep -i proxy  # 看全局
   env | grep -i proxy                          # 看 env
   ```

2. **裸 curl 通不通 github.com**
   ```bash
   curl -sS -o /dev/null -w "HTTP=%{http_code} time=%{time_total}\n" --max-time 5 https://github.com
   # ✅ HTTP 200 → 网络层 OK,问题在 git 配置层
   # ❌ timeout → 真的撞墙,继续下面
   ```

3. **hosts 解析对不对**
   ```bash
   getent hosts github.com
   # 期望:返回可达 IP(如 20.205.243.166 / 140.82.112.3)
   ```

4. **扫描可达 IP**
   ```bash
   ~/bin/ping_github.sh
   # 9 个 GitHub 官方 IP 段 443 端口,看哪些可达
   ```

5. **试 git alias 兜底**
   ```bash
   cd /tmp && git ghub ls-remote https://github.com/<org>/<repo>.git HEAD
   # ✅ exit 0 → alias 走得通,日常用 ghub 即可
   # ❌ timeout → 继续 Fallback 3 / 4
   ```

6. **完整 verbose 看卡哪**
   ```bash
   GIT_CURL_VERBOSE=1 timeout 10 git ls-remote https://github.com/<org>/<repo>.git HEAD 2>&1 | head -30
   # 看 Trying IP / TLS handshake / 证书错误 / proxy refused
   ```

## 工具

### `~/bin/ping_github.sh`

扫描 9 个 GitHub 官方 IP 段 443 端口可达性,撞墙第一手工具:

```bash
#!/bin/bash
for ip in 140.82.112.3 140.82.112.4 140.82.113.3 140.82.114.3 \
          140.82.121.3 140.82.121.4 \
          185.199.108.153 185.199.109.153 185.199.110.153; do
  timeout 3 bash -c "echo > /dev/tcp/$ip/443" 2>/dev/null \
    && echo "✅ $ip:443" || echo "❌ $ip:443"
done
```

(2026-08-01 落地验证:9 个 IP 段 8 个可达,`185.199.108.153` 不可达)

## 当前网络现状(2026-08-01 22:48 smoke 实测)

| 域名 / 端点 | 状态 | 走的路径 |
|---|---|---|
| `github.com:443` | ✅ HTTP 200,5s | `/etc/hosts → 20.205.243.166` |
| `api.github.com:443` | ✅ | 直连 `20.205.243.168` |
| `codeload.github.com` | ✅ | 直连 `20.205.243.165` |
| `objects.githubusercontent.com` | ✅ | 直连 `185.199.108/109/110/111.133` |
| `git push` / `git ls-remote` | ✅ exit 0 | Fallback 1 清完代理后通 |

## 我的失误教训

- **撞墙≠网络问题**:撞墙可能是代理撞了、hosts 过期、SSL 证书、SNI 路由...**先 smoke 全栈,别假设**
- **lesson 库里没写"先看 local .git/config"这步** → 2026-08-01 踩了 30+ 分钟才找到根因。**写撞墙 lesson 必须把这一步放第一条**
- **跨仓 / 跨 session 测试**:smoke 命令在 /tmp 跑通 ≠ 在工作仓跑通。本地 `.git/config` 可能污染
- **MEMORY 里 7/29 写"github.com:443 拒连 140s+"** 当时是真的,8/1 已经自愈(可能是 hosts 那条旧条目生效了,也可能 GFW 路由变了)。**网络状态是动态的,撞墙先 smoke,别信过时的 MEMORY**

## 相关 lesson

- `lessons/contrib/github-dns-443-block-hosts-workaround.md` — Fallback 3 完整内容
- `lessons/contrib/git-push-without-shell-agent.md` — Fallback 4 完整内容
- `lessons/contrib/lesson-08-pip-https-proxy-clash.md` — pip install 的 HTTPS_PROXY 方案(撞墙相关但不是 git)
## Problem

在 WSL2 上 `git push` / `git clone` / `git ls-remote` 卡到 124 超时，但**裸 `curl https://github.com` 反而 HTTP 200**。第一次遇到时很容易判成"网络被墙"，于是去改 hosts、加代理、装 CA——而真正的原因在仓库自己的 `.git/config` 里。

2026-08-01 的实际案例：`Agent-Medici` 仓（已废弃）配了 `http.proxy=socks5://172.19.128.1:7890`，那是一条已经死掉的 Windows Clash 链路。WSL 不继承 Windows 的 git 配置，所以**只有这一个仓**的 git 操作撞墙，其他仓正常——这个"只有部分仓坏"的特征正是本条的第一判据。

## Verification

2026-08-01 22:48 实测：

- `git config --local --list | grep -i proxy` 打出 `[http] proxy = socks5://172.19.128.1:7890` —— 确认 Fallback 1 命中
- `git config --local --unset http.proxy` 后，`git ls-remote` **exit 0 并返回 commit SHA**
- 全栈 smoke：`github.com:443` HTTP 200、`api.github.com:443` ✅、`codeload.github.com` ✅、`objects.githubusercontent.com` ✅
- `~/bin/ping_github.sh`：9 个官方 IP 段中 8 个 443 可达，`185.199.108.153` 不可达

判据：**`curl github.com` 通而 `git ls-remote` 不通，且 local config 里有 proxy 行** —— 三条同时成立即为本条描述的情形；unset proxy 后 `git ls-remote` 必须 exit 0，否则说明不是这一层，继续往 Fallback 2/3/4 走。

未验证：Fallback 2–4 在本条落地的当天没有全部实跑（Fallback 1 修完即通），它们各自的完整验证记录在 `lessons/contrib/github-dns-443-block-hosts-workaround.md` 和 `lessons/contrib/git-push-without-shell-agent.md` 里。
