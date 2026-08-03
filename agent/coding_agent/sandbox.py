"""Sandboxed executor for generated code.

Uses multiprocessing.Process for isolation + timeout.
The SDK objects are constructed inside the child process (shared-nothing).
Static analysis rejects dangerous patterns before execution.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from .schemas import EvidenceBundle, Observation, Measurement


@dataclass
class SandboxResult:
    evidence: EvidenceBundle | None = None
    stdout: str = ""
    stderr: str = ""
    exception: str | None = None
    elapsed_s: float = 0.0
    timed_out: bool = False
    code: str = ""


FORBIDDEN_PATTERNS = [
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "import urllib",
    "import requests",
    "import http",
    "import ftplib",
    "import smtplib",
    "import shutil",
    "import pathlib",
    "import signal",
    "import ctypes",
    "__import__(",
    "eval(",
    "exec(",
    "compile(",
    "breakpoint(",
    "globals(",
    "locals(",
]

FORBIDDEN_FILE_ACCESS = [
    "open(",
    "os.path",
    "os.listdir",
    "os.walk",
    "os.system",
    "os.popen",
]


ALLOWED_IMPORT_ROOTS = {
    "numpy", "np", "cv2", "scipy", "sklearn", "pandas", "pd",
    "networkx", "nx", "shapely", "matplotlib", "math", "collections",
    "itertools", "functools", "dataclasses", "typing", "re",
}


def static_check(code: str) -> str | None:
    """Return error message if code uses forbidden patterns, else None."""
    for pattern in FORBIDDEN_PATTERNS + FORBIDDEN_FILE_ACCESS:
        if pattern in code:
            return f"Forbidden pattern: '{pattern}'"
    if "import " in code:
        import re
        imports = re.findall(r"^\s*(?:from\s+(\S+)|import\s+(\S+))", code, re.MULTILINE)
        for groups in imports:
            mod = (groups[0] or groups[1]).split(".")[0]
            if mod and mod not in ALLOWED_IMPORT_ROOTS:
                return f"Forbidden import: '{mod}'"
    return None


def _worker(code_str: str, video_path: str, question: str, options: list[str],
            artifacts_dir: str, result_queue: multiprocessing.Queue):
    """Run inside child process."""
    import io
    import contextlib

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))

        from agent.coding_agent.sdk.context import SolveContext
        from agent.coding_agent.schemas import EvidenceBundle, Observation, Measurement

        ctx = SolveContext(video_path, question, options, artifacts_dir)

        import numpy as np
        import cv2
        import math
        import re as re_mod
        import collections
        import itertools
        import functools

        import scipy
        import scipy.signal
        import scipy.ndimage
        import scipy.interpolate
        import scipy.optimize
        import scipy.spatial

        ALLOWED_IMPORTS = {
            "numpy": np, "np": np,
            "cv2": cv2,
            "math": math,
            "re": re_mod,
            "collections": collections,
            "itertools": itertools,
            "functools": functools,
            "scipy": scipy,
            "scipy.signal": scipy.signal,
            "scipy.ndimage": scipy.ndimage,
            "scipy.interpolate": scipy.interpolate,
            "scipy.optimize": scipy.optimize,
            "scipy.spatial": scipy.spatial,
        }

        def _restricted_import(name, *args, **kwargs):
            if name in ALLOWED_IMPORTS:
                return ALLOWED_IMPORTS[name]
            top = name.split(".")[0]
            if top in {"numpy", "scipy", "cv2", "math", "re",
                       "collections", "itertools", "functools",
                       "matplotlib", "sklearn", "pandas", "networkx", "shapely"}:
                return __builtins__["_real_import"](name, *args, **kwargs)
            raise ImportError(f"Import of '{name}' is not allowed in sandbox")

        import builtins as _bi
        namespace = {
            "ctx": ctx,
            "np": np,
            "numpy": np,
            "cv2": cv2,
            "math": math,
            "re": re_mod,
            "collections": collections,
            "itertools": itertools,
            "functools": functools,
            "scipy": scipy,
            "EvidenceBundle": EvidenceBundle,
            "Observation": Observation,
            "Measurement": Measurement,
            "__builtins__": {
                "__name__": "__main__",
                "_real_import": _bi.__import__,
                "__import__": _restricted_import,
                "__build_class__": _bi.__build_class__,
                "print": print, "len": len, "range": range, "int": int,
                "float": float, "str": str, "bool": bool, "list": list,
                "dict": dict, "tuple": tuple, "set": set, "frozenset": frozenset,
                "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
                "sorted": sorted, "reversed": reversed, "enumerate": enumerate,
                "zip": zip, "map": map, "filter": filter, "next": next,
                "iter": iter, "any": any, "all": all, "id": id,
                "isinstance": isinstance, "issubclass": issubclass,
                "type": type, "hasattr": hasattr, "getattr": getattr,
                "setattr": setattr, "delattr": delattr,
                "ValueError": ValueError, "TypeError": TypeError,
                "IndexError": IndexError, "KeyError": KeyError,
                "RuntimeError": RuntimeError, "Exception": Exception,
                "AttributeError": AttributeError,
                "StopIteration": StopIteration,
                "NotImplementedError": NotImplementedError,
                "ZeroDivisionError": ZeroDivisionError,
                "OverflowError": OverflowError,
                "AssertionError": AssertionError,
                "IOError": IOError,
                "OSError": OSError,
                "FileNotFoundError": FileNotFoundError,
                "ImportError": ImportError,
                "None": None, "True": True, "False": False,
                "bytes": bytes, "bytearray": bytearray,
                "memoryview": memoryview, "complex": complex,
                "chr": chr, "ord": ord,
                "hex": hex, "oct": oct, "bin": bin,
                "slice": slice, "property": property,
                "staticmethod": staticmethod, "classmethod": classmethod,
                "super": super, "object": object,
                "divmod": divmod, "pow": pow,
                "format": format, "repr": repr,
            },
        }

        with contextlib.redirect_stdout(stdout_buf), \
             contextlib.redirect_stderr(stderr_buf):
            exec(compile(code_str, "<sandbox>", "exec"), namespace)
            if "solve" not in namespace:
                raise RuntimeError("Code must define a function 'solve(ctx)'")
            evidence = namespace["solve"](ctx)

        if not isinstance(evidence, EvidenceBundle):
            evidence = EvidenceBundle(
                execution_status="partial",
                warnings=[f"solve() returned {type(evidence).__name__}, not EvidenceBundle"])

        result_queue.put({
            "evidence": evidence.to_dict(),
            "stdout": stdout_buf.getvalue()[:5000],
            "stderr": stderr_buf.getvalue()[:5000],
        })

    except Exception as e:
        tb = traceback.format_exc()
        result_queue.put({
            "evidence": None,
            "stdout": stdout_buf.getvalue()[:5000],
            "stderr": stderr_buf.getvalue()[:5000],
            "exception": f"{type(e).__name__}: {e}\n{tb[-2000:]}",
        })


def execute_in_sandbox(code_str: str, video_path: str, question: str,
                       options: list[str], artifacts_dir: str | None = None,
                       timeout: int = 120) -> SandboxResult:
    """Execute generated code in an isolated process.

    Args:
        code_str: Python source defining `def solve(ctx) -> EvidenceBundle`.
        video_path: absolute path to video file.
        question: the question text.
        options: answer options.
        artifacts_dir: directory for visualization outputs.
        timeout: max execution time in seconds.

    Returns:
        SandboxResult with evidence, stdout/stderr, exception info.
    """
    err = static_check(code_str)
    if err:
        return SandboxResult(exception=err, code=code_str)

    if artifacts_dir is None:
        import tempfile
        artifacts_dir = tempfile.mkdtemp(prefix="vistr_sandbox_")
    os.makedirs(artifacts_dir, exist_ok=True)

    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_worker,
                    args=(code_str, video_path, question, options, artifacts_dir, q))

    t0 = time.time()
    p.start()
    p.join(timeout=timeout)
    elapsed = time.time() - t0

    if p.is_alive():
        p.terminate()
        p.join(timeout=5)
        if p.is_alive():
            p.kill()
        return SandboxResult(timed_out=True, elapsed_s=elapsed, code=code_str)

    if q.empty():
        return SandboxResult(
            exception="Process exited without result (possibly OOM or crash)",
            elapsed_s=elapsed, code=code_str)

    result = q.get_nowait()
    evidence = None
    if result.get("evidence"):
        d = result["evidence"]
        evidence = EvidenceBundle(
            execution_status=d["execution_status"],
            observations=[Observation(**o) for o in d.get("observations", [])],
            measurements=[Measurement(**m) for m in d.get("measurements", [])],
            artifacts=d.get("artifacts", []),
            warnings=d.get("warnings", []),
            limitations=d.get("limitations", []),
        )

    return SandboxResult(
        evidence=evidence,
        stdout=result.get("stdout", ""),
        stderr=result.get("stderr", ""),
        exception=result.get("exception"),
        elapsed_s=elapsed,
        code=code_str,
    )
