I'll start by exploring the repository structure to understand the conventions before writing anything.

<tool_call>
<function=Bash>
<parameter=command>
ls -la && echo "---DOCS---" && ls -la docs/maintainer/ 2>/dev/null && echo "---LESSONS---" && ls -la lessons/ 2>/dev/null && echo "---SCRIPTS---" && ls -la scripts/ 2>/dev/null && echo "---TESTS---" && ls -la tests/ 2>/dev/null
</parameter>
<parameter=description>
List repository structure
</parameter>
</function>
</tool_call>