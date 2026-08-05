---
title: bootstrap 这也是倒吊人的操作 二 当前未解决的 3 个问题 问题 1 hermes run 命令仍然找不到
domain: devops
tags:
- node:hermes_wsl
- source:bootstrap
- project:hermes
source: bootstrap
status: draft
created: '2026-04-01'
confidence: 0.7
---


## 背景
[assistant] <think>
Wait, it worked! `hermes is a function` - the function is found and defined. And `HERMES_INNER=1 bash -c 'source ~/.bashrc_alias && _hermes_bin --version' _ --version` should work. But then wh

## 用户描述
这也是倒吊人的操作：二、当前未解决的 3 个问题
问题 1：hermes\-run 命令仍然找不到
\- 根因：WSL 里 wsl \-e bash \-c '...' 启动的是非交互式 shell，不自动 source .bashrc
\- BASH\_ENV 写在 .bashrc 里没用（chicken\-and\-egg）
\- \~/.bashrc\_alias 里有正确的 function，但非交互式 shell 根本读不到它
问题 2：需要 sudo 才能完成的修复
\- /etc/environment 无法写入（Permission denied），需要 sudo 才能加 BASH\_ENV
\- 或者需要你在 WSL 里手动执行 sudo systemctl disable \-\-now wsl\-pro.service
问题 3：调试污染
\- .bashrc 里残留了 echo "BASHRC\_SOURCED" 调试行和 export BASH\_ENV=\~/.bashrc\_env.sh（目前无效，需要清理或保留取决于问题1的解法）
最快解法：你在 WSL

## 助理回复
<think>
The user is sharing Hanged Man's notes about the remaining problems. The key issue is that WSL's `wsl -e bash -c '...'` spawns a non-interactive shell that doesn't source .bashrc. The BASH_ENV trick doesn't work because it's in .bashrc itself.

But looking at the actual WSL terminal output from the user:
```
C:\Users\Eric Jia>WSL
eric_jia@localhost:/mnt/c/Users/Eric Jia$ Hermes
Hermes: command not found
```

Wait - the user typed `Hermes` (capital H), not `hermes`! Case sensitivity! WSL bash is case-sensitive. 

Though I should note that Windows terminals typically preserve case when passing commands to WSL, so the capitalization might not be the actual issue here. Let me reconsider what's happening with the shell initialization. When `wsl` is invoked from CMD without arguments, it

