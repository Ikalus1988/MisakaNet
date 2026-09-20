Let me start by exploring the repository structure to understand the codebase and existing documentation.

<tool_call>
<function=Bash>
<parameter=command>
find /testbed -type f -name "*.md" | head -50
</parameter>
<parameter=description>
Find markdown files in the repo
</parameter>
</function>
</tool_call>
<tool_call>
<function=Bash>
<parameter=command>
ls -la /testbed
</parameter>
<parameter=description>
List top-level directory contents
</parameter>
</function>
</tool_call>