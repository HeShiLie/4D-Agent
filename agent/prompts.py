"""Phase-2 plan/verify prompts v2（用户 2026-08-01 修正的设计）:

- PLAN（planner）: 分步计划 + 每一步该拿到什么 evidence（规格化），最后给初步答案（兼作 baseline）
- VERIFY（verifier，隔离上下文）: 看不到 planner 的答案，只能看到 planner 的证据清单；
  针对每条 evidence 制定严格验收标准 + 反欺骗检查（防止 planner 自己骗自己），
  再独立逐条核对帧内容，给出 verdict。

v1（盲 checklist）留存于 prompts_v1 注释，部分结果已归档 outputs/plan_verify/*_v1_partial.jsonl。
"""

PLAN_PROMPT = """你是一个时空推理任务的**规划器（planner）**。上面是一段视频均匀抽出的 {n} 帧（按时间顺序）。题目如下：

【题目】{question}

你的任务是制定一个分步解题计划，并为每一步明确**该拿到的证据（evidence）**——后续会有独立的验收员（verifier）针对你的证据清单制定验收标准来审计你，所以你的证据规格必须具体、可观测、可核验。

严格按以下结构输出（用中文，术语可保留英文）：

<plan>
步骤 1:
- 目标：这一步要确定什么
- evidence：这一步必须拿到的证据。务必具体到：看哪个目标/区域/哪几帧/什么运动量或几何量，拿到后能排除什么错误可能
- 获取方式：打算怎么拿到（直接观察帧 / 目标检测跟踪 / 光流 / 人体姿态估计 / 3D 重建 / 局部放大 / 轨迹拟合 …可自由提出工具）
步骤 2: ...
（2-5 步）
</plan>

最后，基于你目前能直接观察到的内容，给出初步判断（验收员看不到这个答案）：
<answer>{option_a} 或 {option_b} 之一</answer>
<confidence>0-100 的整数</confidence>"""

VERIFY_PROMPT = """你是一个独立**验收员（verifier）**，职责是防止规划器自欺欺人。上面是一段视频均匀抽出的 {n} 帧（按时间顺序）。题目如下：

【题目】{question}

下面是某规划器为回答此题制定的计划与证据清单。你看不到它的答案，也不需要猜它的答案。

【规划器的计划】
{plan_text}

请完成两件事，严格按以下结构输出（用中文）：

<acceptance_criteria>
针对计划中每一条 evidence：
- 验收标准：什么样的观察结果才算这条证据真实成立（给出具体的判定依据：区域/时刻/阈值/形态）
- 反欺骗检查：规划器在这条上最可能怎么糊弄（如：措辞含糊、以偏概全、把单帧当趋势、忽略相机自身运动、把相关当因果、只看想看的帧）——验收时必须额外核对什么
</acceptance_criteria>

<self_check>
由你（而非规划器）逐条对照帧内容独立核对：每条 evidence 实际观察结果是 成立/不成立/无法判断 + 一句依据
</self_check>

最后给出你自己的判定：
<answer>{option_a} 或 {option_b} 之一</answer>
<confidence>0-100 的整数</confidence>"""


def build_messages(prompt_tmpl, question, options, frames_b64, plan_text=""):
    """User message: text prompt + frames (as base64 image urls)."""
    option_a, option_b = options
    text = prompt_tmpl.format(n=len(frames_b64), question=question,
                              option_a=option_a, option_b=option_b,
                              plan_text=plan_text or "（无）")
    content = [{"type": "text", "text": text}]
    for b in frames_b64:
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + b}})
    return [{"role": "user", "content": content}]
