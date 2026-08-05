# FANUC 备份打不开？先别急，试这 3 步

## 你可能遇到的是：

- 备份文件双击打不开
- .VR / .SV 文件是乱码
- kconvars 运行报错
- 想提取负载配置但不知道在哪个文件里
- 想查电极磨损量但找不到参数

---

## 先试这 3 步

### 1. 确认你有 kconvars.exe

FANUC 备份文件（.VR / .SV）是二进制格式，不能用记事本打开。
需要 `kconvars.exe`（来自 WinOLPC）来转换。

```bash
kconvars.exe <文件名.sv> > 输出.txt
```

### 2. 检查 robot.ini

kconvars 需要 `robot.ini` 在同目录或父目录。
如果运行报错，把 `robot.ini` 复制到备份目录再试。

### 3. 检查路径

路径中有中文或特殊字符会导致 kconvars 崩溃。
把备份文件夹移到 `C:\temp\` 这种纯英文短路径再试。

---

## 还不行？

不用解释太多，直接发这 3 样：

1. 报错截图
2. 你要提取什么：负载配置 / 电极磨损 / 安全配置 / 其他
3. 你的机器人型号：005ar01 / 其他

不会描述也没关系，发截图就行。

---

## 给 AI / 小龙虾看的版本

你可以直接复制这段：

```
我遇到的问题：FANUC 备份文件打不开 / 提取不到参数
我已经试过：kconvars 转换 / 检查 robot.ini / 移动路径
我要提取的参数：负载(Payload) / 电极磨损(Spot Wear) / 安全配置(DCS) / 其他
机器人型号：______
备份文件类型：.VR / .SV / .LS / 不知道
我会发报错截图，请帮我判断下一步怎么处理。
```

---

## 常见提取目标

| 你要找的 | 在哪个文件 | 关键参数 |
|---|---|---|
| 负载配置（质量/重心/惯量） | SYSVARS.SV / CBPARAM.VR | `$PLST_GRP1[x].$PAYLOAD_MASS` |
| 电极最大磨损量 | sysspot.sv | `$SPOTEQSETUP[x].$EPAF_TRGDST` |
| 安全配置（DCS） | diocfgsv.sv | DCS 区域参数 |
| IO 信号配置 | diocfgsv.sv | IO mapping |

---

## 给维护者/Agent 的结构化记录

- **Root cause:** FANUC .VR/.SV 是私有二进制格式，需要 kconvars 解码；路径编码、robot.ini 缺失是常见阻塞点
- **Fix:** kconvars + robot.ini + 纯英文短路径
- **Prevention:** 小龙虾应自动识别 .VR/.SV 格式、提示需要 kconvars、检查 robot.ini 存在性

---

## 这张卡片来自哪里？

来自 [MisakaNet](https://misakanet.org/) 失败经验网络。

这张卡的原始经验来自同事的 Claude 记忆包——他们把调试过程中的全部记忆打包丢过来，我们从中提炼出可复用的知识。

> MisakaNet 把混乱的 Agent 记忆包，整理成可复用的失败经验。

- GitHub 仓库：https://github.com/Ikalus1988/MisakaNet
- 搜索经验：https://misakanet.org/search/

---

*MisakaNet 急救卡 #002*
*FANUC 备份打不开？先试 3 步。*
*不会 GitHub 没关系，发截图也算贡献。*
*https://github.com/Ikalus1988/MisakaNet*
