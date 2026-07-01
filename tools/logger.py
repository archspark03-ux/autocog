"""
tools/logger.py — Rəngli, fayl və konsol logları.
Kiber estetikası: qara arxa plan, yaşıl/sarı/mətni rəngli.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

# Ranglar
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
RED = "\x1b[31m"
MAGENTA = "\x1b[35m"
CYAN = "\x1b[36m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def setup_file_logger(name: str, log_dir: Path) -> logging.Logger:
    """Fayla yazan logger qur (gündəlik fayl, köhnələr sıxışdırıla bilər)."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger
    log_dir.mkdir(parents=True, exist_ok=True)
    # Gündəlik log faylı (log_rotation tərəfindən rotasiya olunur)
    date_str = datetime.now().strftime("%Y-%m-%d")
    fh = logging.FileHandler(log_dir / f"{name}-{date_str}.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)
    return logger


# Konsol helper-ləri
def info(msg: str) -> None:
    print(f"{DIM}{_now()}{RESET} {GREEN}●{RESET} {msg}")


def step(msg: str) -> None:
    print(f"{DIM}{_now()}{RESET} {CYAN}▶{RESET} {BOLD}{msg}{RESET}")


def think(msg: str) -> None:
    print(f"{DIM}{_now()}{RESET} {MAGENTA}◆{RESET} {MAGENTA}{msg}{RESET}")


def research(msg: str) -> None:
    print(f"{DIM}{_now()}{RESET} {BLUE}⌕{RESET} {BLUE}{msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{DIM}{_now()}{RESET} {YELLOW}⚠{RESET} {YELLOW}{msg}{RESET}")


def error(msg: str) -> None:
    print(f"{DIM}{_now()}{RESET} {RED}✖{RESET} {RED}{msg}{RESET}")


def success(msg: str) -> None:
    print(f"{DIM}{_now()}{RESET} {GREEN}✓{RESET} {BOLD}{GREEN}{msg}{RESET}")


def banner(title: str) -> None:
    """Böyük başlıq."""
    line = "═" * (len(title) + 4)
    print(f"\n{BOLD}{CYAN}{line}{RESET}")
    print(f"{BOLD}{CYAN}║ {title} ║{RESET}")
    print(f"{BOLD}{CYAN}{line}{RESET}\n")


def section(title: str) -> None:
    """Kiçik başlıq."""
    print(f"\n{BOLD}{YELLOW}── {title} ──{RESET}")


def dump(text: str, max_lines: int = 20) -> None:
    """Çox uzun mətni qısaldıb göstər."""
    lines = text.splitlines() or [text]
    if len(lines) <= max_lines:
        for ln in lines:
            print(f"    {DIM}{ln}{RESET}")
    else:
        head = lines[: max_lines // 2]
        tail = lines[-(max_lines // 2):]
        for ln in head:
            print(f"    {DIM}{ln}{RESET}")
        print(f"    {DIM}… ({len(lines) - max_lines} sətir buraxıldı) …{RESET}")
        for ln in tail:
            print(f"    {DIM}{ln}{RESET}")
