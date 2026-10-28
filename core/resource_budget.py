"""Refuse optional model work before it consumes the OS drive's paging headroom."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import shutil


class ResourceBudgetError(RuntimeError):
    pass


def process_memory():
    if os.name != "nt":
        return None
    from ctypes import wintypes as w

    class Counters(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("page_faults", w.DWORD),
                    *[(name, ctypes.c_size_t) for name in (
                        "peak_working_set", "working_set", "peak_paged_pool", "paged_pool",
                        "peak_nonpaged_pool", "nonpaged_pool", "pagefile", "peak_pagefile", "private")]]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.K32GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD]
    counters = Counters()
    counters.size = ctypes.sizeof(counters)
    if not kernel.K32GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.size):
        return None
    return {"working_set_mb": counters.working_set // 1024 ** 2, "private_commit_mb": counters.private // 1024 ** 2,
            "peak_working_set_mb": counters.peak_working_set // 1024 ** 2}


def memory_headroom():
    if os.name != "nt":
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                    *[(name, ctypes.c_ulonglong) for name in (
                        "total_physical", "available_physical", "total_commit", "available_commit",
                        "total_virtual", "available_virtual", "extended_virtual")]]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ResourceBudgetError("Unable to check available memory before model inference.")
    return {"available_ram_mb": status.available_physical // 1024 ** 2,
            "available_commit_mb": status.available_commit // 1024 ** 2}


def check_model_budget(required_mb=768):
    system = Path(os.environ.get("SystemDrive", Path.home().anchor or "/") + ("\\" if os.name == "nt" else ""))
    minimum_gb = float(os.getenv("CINESCENE_MIN_SYSTEM_FREE_GB", "3"))
    if shutil.disk_usage(system).free < minimum_gb * 1024 ** 3:
        raise ResourceBudgetError("Model processing paused: the system drive has insufficient free space. No model was loaded.")
    headroom = memory_headroom()
    reserve = int(os.getenv("CINESCENE_RAM_RESERVE_MB", "384"))
    if headroom and (headroom["available_ram_mb"] < required_mb + reserve or
                     headroom["available_commit_mb"] < required_mb + reserve):
        raise ResourceBudgetError("Model processing paused: insufficient available memory. Close other memory-heavy applications and retry.")
    return headroom
