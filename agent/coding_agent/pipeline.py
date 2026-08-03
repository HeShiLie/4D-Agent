"""Coding Agent pipeline: Plan → Execute → Verify.

Model-driven: VLM selects JSON actions → action_executor runs pre-built
analysis code → verifier judges from evidence + frames.
No free-form codegen. No task-field routing.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import tempfile
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from agent import llm
from agent.coding_agent.sandbox import execute_in_sandbox, SandboxResult
from agent.coding_agent.schemas import EvidenceBundle
from agent.coding_agent.action_executor import execute_plan
from agent.coding_agent.prompts.planner import PLANNER_PROMPT
from agent.coding_agent.prompts.verifier import (
    VERIFIER_PROMPT, VLM_OBSERVE_PROMPT, VLM_JUDGE_PROMPT,
    HYBRID_JUDGE_PROMPT, VLM_COT_PROMPT,
)
from agent.coding_agent.recipes import select_recipe_by_content
from agent.coding_agent.sdk.context import SolveContext
from agent.tools import BENCH_DIR


def _frames_b64(video_path: str, n: int = 8) -> list[str]:
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for j in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(j * (total - 1) / max(n - 1, 1)))
        ok, fr = cap.read()
        if ok:
            fr = cv2.resize(fr, (640, 360))
            out.append(base64.b64encode(
                cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 65])[1]).decode())
    cap.release()
    return out


def _extract_json(text: str) -> dict:
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def _extract_code(text: str) -> str:
    m = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        code = m.group(1)
    else:
        m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            code = m.group(1)
        elif "def solve" in text:
            code = text[text.index("def solve"):]
        else:
            code = text
    lines = code.split("\n")
    cleaned = [l for l in lines
               if not l.strip().startswith("import ")
               and not l.strip().startswith("from ")]
    return "\n".join(cleaned)


def step_plan(question: str, options: list[str], frames_b64: list[str]) -> dict:
    prompt = PLANNER_PROMPT.format(
        question=question, options=" / ".join(options))
    content = [{"type": "text", "text": prompt}]
    for b in frames_b64:
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + b}})
    resp = llm.chat([{"role": "user", "content": content}],
                    max_tokens=500, temperature=0.0, retries=3)
    return _extract_json(resp["content"])


def step_execute_actions(plan: dict, video_path: str,
                         question: str, options: list[str]) -> EvidenceBundle:
    """Run the pre-built action executor — no sandbox needed."""
    artifacts_dir = tempfile.mkdtemp(prefix="vistr_art_")
    ctx = SolveContext(video_path, question, options, artifacts_dir)
    return execute_plan(ctx, plan)


def step_execute_recipe(recipe_code: str, video_path: str,
                        question: str, options: list[str],
                        timeout: int = 120) -> SandboxResult:
    """Run a matched recipe in sandbox."""
    artifacts_dir = tempfile.mkdtemp(prefix="vistr_art_")
    return execute_in_sandbox(recipe_code, video_path, question, options,
                              artifacts_dir=artifacts_dir, timeout=timeout)


def step_verify(question: str, options: list[str], evidence: EvidenceBundle,
                frames_b64: list[str]) -> str:
    prompt = VERIFIER_PROMPT.format(
        question=question,
        options=" / ".join(options),
        evidence_text=evidence.summary_text(),
    )
    content = [{"type": "text", "text": prompt}]
    for b in frames_b64[:4]:
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + b}})
    resp = llm.chat([{"role": "user", "content": content}],
                    max_tokens=30, temperature=0.0, retries=3)
    answer = resp["content"].strip().strip("。.")
    for o in options:
        if o.lower() in answer.lower():
            return o
    return answer


def step_hybrid_verify(question: str, options: list[str],
                       evidence: EvidenceBundle, frames_b64: list[str]) -> tuple[str, str]:
    """VLM observe first, then judge using both observations and tool evidence."""
    obs_prompt = VLM_OBSERVE_PROMPT.format(
        question=question, options=" / ".join(options))
    obs_content = [{"type": "text", "text": obs_prompt}]
    for b in frames_b64:
        obs_content.append({"type": "image_url",
                            "image_url": {"url": "data:image/jpeg;base64," + b}})
    obs_resp = llm.chat([{"role": "user", "content": obs_content}],
                        max_tokens=300, temperature=0.0, retries=3)
    observations = obs_resp["content"].strip()

    judge_prompt = HYBRID_JUDGE_PROMPT.format(
        question=question, options=" / ".join(options),
        observations=observations,
        evidence_text=evidence.summary_text())
    judge_content = [{"type": "text", "text": judge_prompt}]
    for b in frames_b64[:4]:
        judge_content.append({"type": "image_url",
                              "image_url": {"url": "data:image/jpeg;base64," + b}})
    judge_resp = llm.chat([{"role": "user", "content": judge_content}],
                          max_tokens=30, temperature=0.0, retries=3)
    answer = judge_resp["content"].strip().strip("。.")
    for o in options:
        if o.lower() in answer.lower():
            return o, observations
    return answer, observations


def vlm_cot(question: str, options: list[str],
            frames_b64: list[str]) -> tuple[str, str]:
    """Single-step CoT: observe + reason + answer in one call."""
    prompt = VLM_COT_PROMPT.format(
        question=question, options=" / ".join(options))
    content = [{"type": "text", "text": prompt}]
    for b in frames_b64:
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + b}})
    resp = llm.chat([{"role": "user", "content": content}],
                    max_tokens=500, temperature=0.0, retries=3)
    full_text = resp["content"].strip()
    last_line = full_text.strip().split("\n")[-1].strip().strip("。.")
    for o in options:
        if o.lower() in last_line.lower():
            return o, full_text
    for o in options:
        if o.lower() in full_text.lower():
            return o, full_text
    return last_line, full_text


def vlm_observe_and_judge(question: str, options: list[str],
                          frames_b64: list[str]) -> tuple[str, str]:
    obs_prompt = VLM_OBSERVE_PROMPT.format(
        question=question, options=" / ".join(options))
    obs_content = [{"type": "text", "text": obs_prompt}]
    for b in frames_b64:
        obs_content.append({"type": "image_url",
                            "image_url": {"url": "data:image/jpeg;base64," + b}})
    obs_resp = llm.chat([{"role": "user", "content": obs_content}],
                        max_tokens=300, temperature=0.0, retries=3)
    observations = obs_resp["content"].strip()

    judge_prompt = VLM_JUDGE_PROMPT.format(
        question=question, options=" / ".join(options),
        observations=observations)
    judge_content = [{"type": "text", "text": judge_prompt}]
    for b in frames_b64[:4]:
        judge_content.append({"type": "image_url",
                              "image_url": {"url": "data:image/jpeg;base64," + b}})
    judge_resp = llm.chat([{"role": "user", "content": judge_content}],
                          max_tokens=30, temperature=0.0, retries=3)
    answer = judge_resp["content"].strip().strip("。.")
    for o in options:
        if o.lower() in answer.lower():
            return o, observations
    return answer, observations


def solve_sample(sample: dict, timeout: int = 120) -> dict:
    """Model-driven pipeline — plan JSON actions, execute, verify.

    Flow:
      1. Plan → model selects 1-3 actions from a menu
      2. Recipe check → if keyword match, run recipe in sandbox
      3. Action executor → run pre-built code for each action
      4. Verify → judge answer from evidence + frames
      5. Fallback → VLM observe+judge if evidence is empty/garbage
    """
    video_path = os.path.join(BENCH_DIR, sample["video"])
    question = sample["direct_prompting"]
    options = sample["options"]
    task = sample["task"]
    gt = sample["answer"]

    try:
        t0 = time.time()
        frames_b64 = _frames_b64(video_path, n=8)

        # Step 1: Plan — model decides what to analyze
        plan = step_plan(question, options, frames_b64)

        # Step 2: Check recipes by content
        recipe_code = select_recipe_by_content(question, plan)

        evidence = None
        src = "action_plan"
        code_str = ""

        if recipe_code:
            # Recipe matched — run in sandbox (proven code)
            result = step_execute_recipe(recipe_code, video_path,
                                         question, options, timeout=timeout)
            if result.evidence and result.evidence.execution_status in ("success", "partial"):
                evidence = result.evidence
                src = "recipe"
                code_str = recipe_code[:3000]

        if evidence is None:
            # No recipe or recipe failed — run action executor
            plan_actions = {a.get("action") for a in plan.get("actions", [])}
            plan_actions.discard("visual_observation")

            if not plan_actions:
                # VLM-only plan — skip tool execution
                pred, observations = vlm_observe_and_judge(
                    question, options, frames_b64)
                evidence_text = f"[plan: visual_observation]\n{observations}"
                src = "vlm_observe_judge"
                elapsed = time.time() - t0
                return {
                    "id": sample["id"], "task": task, "gt": gt,
                    "pred": pred, "correct": pred == gt,
                    "src": src,
                    "question": question, "options": options,
                    "video": sample.get("video", ""),
                    "dimension": sample.get("dimension", ""),
                    "evidence": evidence_text,
                    "analysis_spec": plan,
                    "elapsed_s": elapsed,
                }

            # Execute the plan actions
            evidence = step_execute_actions(plan, video_path, question, options)

        # Check if evidence is useful
        has_useful = (
            evidence.execution_status in ("success", "partial")
            and (evidence.observations or evidence.measurements)
        )

        if has_useful:
            # VLM observe first, then judge with evidence as supplement
            pred, observations = step_hybrid_verify(
                question, options, evidence, frames_b64)
            evidence_text = (
                f"[hybrid: VLM + tool]\nVisual: {observations}\n"
                f"Tool: {evidence.summary_text()}"
            )
            src = "hybrid"
        else:
            # Evidence is garbage — fall back to VLM observe+judge
            pred, observations = vlm_observe_and_judge(
                question, options, frames_b64)
            evidence_text = (
                f"[action plan produced no useful evidence, VLM fallback]\n"
                f"Warnings: {evidence.warnings}\n{observations}"
            )
            src = "vlm_fallback"

        elapsed = time.time() - t0
        return {
            "id": sample["id"], "task": task, "gt": gt,
            "pred": pred, "correct": pred == gt,
            "src": src,
            "question": question, "options": options,
            "video": sample.get("video", ""),
            "dimension": sample.get("dimension", ""),
            "evidence": evidence_text,
            "code": code_str,
            "analysis_spec": plan,
            "elapsed_s": elapsed,
            "error": None,
        }

    except Exception as e:
        import traceback
        return {
            "id": sample["id"], "task": task, "gt": gt,
            "pred": None, "correct": False,
            "src": "error",
            "question": question, "options": options,
            "video": sample.get("video", ""),
            "dimension": sample.get("dimension", ""),
            "error": f"{type(e).__name__}: {str(e)[:300]}",
            "traceback": traceback.format_exc()[-500:],
        }
