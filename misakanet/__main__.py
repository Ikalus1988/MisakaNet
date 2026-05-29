"""MisakaNet — 分布式 AI Agent 经验知识共享系统。

用法:
    python3 -m misakanet            # 显示本帮助
    python3 search_knowledge.py     # 搜索
    python3 scripts/setup.py        # 安装向导
"""
import sys

USAGE = """MisakaNet — 虫群知识共享系统

子命令（在当前版本中）:
    python3 search_knowledge.py "关键词"    BM25 搜索
    python3 scripts/setup.py --check        环境检查
    python3 scripts/new_lesson.py           贡献 lesson
    python3 scripts/score_lessons.py        质量评分
    python3 scripts/contribute.py           一键贡献 PR
    python3 hub/misaka_hub.py               Hub 仲裁服务

在线文档: https://github.com/Ikalus1988/MisakaNet
"""


def main():
    print(USAGE)


if __name__ == "__main__":
    main()
