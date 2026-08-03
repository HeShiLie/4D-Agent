"""Step 4: Self-check and repair prompt."""

SELFCHECK_PROMPT = """以下代码在沙箱中执行出错或结果不完整，请修复。

## 原始代码
```python
{code}
```

## 执行结果
- 状态: {status}
- 异常: {exception}
- 标准输出: {stdout}
- 标准错误: {stderr}
- 警告: {warnings}

## 常见问题
- SDK方法名拼写错误
- 返回类型不匹配（确保返回EvidenceBundle）
- 空结果未处理（检测/跟踪可能返回空列表）
- 数组索引越界
- 帧数不足时的除零错误

## 要求
修复代码使其能正确执行并返回有效的EvidenceBundle。
保持原有分析逻辑不变，只修复执行错误。

只输出修复后的完整Python代码（用```python```包裹）。"""
