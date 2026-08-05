# MisakaNet 演示
# 用法: vhs demo.tape
# 输出: demo.gif
# 要求: vhs (https://github.com/charmbracelet/vhs)

Output demo.gif
Set FontSize 14
Set Width 800
Set Height 400

# 搜索演示
Type "python3 search_knowledge.py 'pip install timeout' --top=1"
Sleep 100ms
Enter
Sleep 3s

# 推荐链
Type "python3 scripts/referral.py"
Sleep 100ms
Enter
Sleep 2s
