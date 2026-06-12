---
{"title": "pip install 网络超时 / SSL / 依赖冲突修复", "domain": "devops", "source": "hermes_wsl", "status": "published", "tags": [], "created": "2026-05-01 08:00 UTC", "updated": "2026-05-01 08:00 UTC"}
---



## 问题

pip install 或 conda install 失败，常见场景：
- 网络超时（TLS handshake timeout）
- SSL 证书验证失败（CERTIFICATE_VERIFY_FAILED）
- 依赖版本冲突（version conflict / incompatible）

## 根因

- 网络问题：国内访问 pypi.org / conda-forge 不稳定
- SSL：系统 CA 证书过期或被代理截持
- 冲突：多个包依赖同一库的不同版本

## 修复

**网络超时 / SSL：**
```bash
# 方案 1：换国内镜像
pip install -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com <package>

# 方案 2：忽略 SSL 验证（临时）
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>

# 方案 3：升级 pip 和 certifi
python -m pip install --upgrade pip certifi
```

**依赖冲突：**
```bash
# 查看冲突详情
pip install <package> 2>&1 | grep -i conflict

# 用虚拟环境隔离
python -m venv ~/.hermes/venv
source ~/.hermes/venv/bin/activate
pip install <package>
```

## 验证

```bash
pip install <package> && python -c "import <package>; print('OK')"
```

## 关联

- WSL 环境下优先用系统 pip，不要用 conda（conda 在 WSL 里路径问题多）