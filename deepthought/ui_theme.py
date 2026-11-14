"""
deepthought.ui_theme
24-bit / 256-color ANSI & Unicode Terminal UI Engine for 1337 / 42 Deepthought Kit.

Combines visual design patterns from:
- JCluzet/42_EXAM (VIP status header, live grading progression, practice toggles)
- wkratos/42-examshell (Interactive track selector, timer & cooldown bars)
- k11q/mini-moulinette (Module scorecard tables, syntax-colored unified diffs)
- piscine_forge/rich_ui.py & theme.py (4 cluster themes: 42-cluster, jcluzet-exam,
  tokyo-night, gruvbox)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import os
import re
import select
import shutil
import signal
import sys
from typing import Any

try:
    import termios
except ImportError:
    termios = None  # type: ignore[assignment]


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[78]")
SGR_TOKEN_RE = re.compile(r"(\x1b\[[0-9;]*m)")

# 42 emblem as drawn in the standard 42 file header.
EMBLEM_42 = (
    "       :::      ::::::::",
    "     :+:      :+:    :+:",
    "   +:+ +:+         +:+",
    " +#+  +:+       +#+",
    "+#+#+#+#+#+   +#+",
    "     #+#    #+#",
    "    ###   ########.fr",
)

# Wordmarks rendered once with the FIGlet "small" font and embedded as data.
TOOL_WORDMARKS = {
    "examshell": (
        "                       _        _ _",
        " _____ ____ _ _ __  __| |_  ___| | |",
        "/ -_) \\ / _` | '  \\(_-< ' \\/ -_) | |",
        "\\___/_\\_\\__,_|_|_|_/__/_||_\\___|_|_|",
    ),
    "moulinette": (
        "                _ _          _   _",
        " _ __  ___ _  _| (_)_ _  ___| |_| |_ ___",
        "| '  \\/ _ \\ || | | | ' \\/ -_)  _|  _/ -_)",
        "|_|_|_\\___/\\_,_|_|_|_||_\\___|\\__|\\__\\___|",
    ),
}


@dataclass(frozen=True)
class ColorPalette:
    """ANSI SGR color palette definition for terminal themes."""

    name: str
    primary: str  # Main frame / brand accent
    secondary: str  # Headers / keys
    ok: str  # Moulinette OK / diff +
    ko: str  # Moulinette KO / diff -
    warn: str  # Cooldown / timer / warnings
    purple: str  # Oracle / VIP badge
    muted: str  # Borders / subtle text
    bold: str  # Bright white bold
    cmd: str  # Shell commands `$> ...`
    reset: str = "\033[0m"


PALETTES: dict[str, ColorPalette] = {
    "42-cluster": ColorPalette(
        name="42-cluster",
        primary="\033[1m",  # Bold white
        secondary="\033[36m",  # Classic ANSI cyan
        ok="\033[32m",  # Standard green
        ko="\033[31m",  # Standard red
        warn="\033[33m",  # Standard yellow
        purple="\033[35m",  # Standard magenta
        muted="\033[2m",  # Dim
        bold="\033[1m",  # Bold
        cmd="\033[36m",  # Cyan
    ),
    "jcluzet-exam": ColorPalette(
        name="jcluzet-exam",
        primary="\033[38;2;0;255;135m",  # #00FF87 Neon Exam Green
        secondary="\033[38;2;0;215;255m",  # #00D7FF Electric Cyan
        ok="\033[1;38;2;0;255;135m",
        ko="\033[1;38;2;255;59;92m",  # #FF3B5C High-Contrast Red
        warn="\033[1;38;2;255;214;10m",  # #FFD60A Gold
        purple="\033[1;38;2;215;95;255m",  # #D75FFF VIP Magenta
        muted="\033[38;2;120;130;145m",
        bold="\033[1;97m",
        cmd="\033[38;2;255;214;10m",
    ),
    "tokyo-night": ColorPalette(
        name="tokyo-night",
        primary="\033[38;2;122;162;247m",  # #7AA2F7
        secondary="\033[38;2;125;207;255m",  # #7DCFFF
        ok="\033[38;2;158;206;106m",  # #9ECE6A
        ko="\033[38;2;247;118;142m",  # #F7768E
        warn="\033[38;2;224;175;104m",  # #E0AF68
        purple="\033[38;2;187;154;247m",  # #BB9AF7
        muted="\033[38;2;86;95;137m",  # #565F89
        bold="\033[1;38;2;192;202;245m",
        cmd="\033[38;2;125;207;255m",
    ),
    "gruvbox": ColorPalette(
        name="gruvbox",
        primary="\033[38;2;250;189;47m",  # #FABD2F
        secondary="\033[38;2;131;165;152m",  # #83A598
        ok="\033[38;2;184;187;38m",  # #B8BB26
        ko="\033[38;2;251;73;52m",  # #FB4934
        warn="\033[38;2;254;128;25m",  # #FE8019
        purple="\033[38;2;211;134;155m",  # #D3869B
        muted="\033[38;2;146;131;116m",  # #928374
        bold="\033[1;38;2;235;219;178m",
        cmd="\033[38;2;142;192;124m",
    ),
}


def _char_display_width(ch: str) -> int:
    """Compute terminal column width of a single Unicode codepoint per UAX #11."""
    import unicodedata

    if unicodedata.combining(ch):
        return 0
    cat = unicodedata.category(ch)
    if cat in ("Cc", "Cf"):
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    return 1


def visible_len(s: str) -> int:
    """Return terminal display column width of string excluding ANSI escapes."""
    clean = ANSI_ESCAPE_RE.sub("", s)
    return sum(_char_display_width(ch) for ch in clean)


def clip_visible(s: str, max_cols: int) -> str:
    """Clip a string (preserving ANSI SGR color codes) to at most `max_cols` terminal columns."""
    if max_cols <= 0:
        return ""
    if visible_len(s) <= max_cols:
        return s
    parts = SGR_TOKEN_RE.split(s)
    out: list[str] = []
    seen_sgr = False
    rem = max_cols
    for part in parts:
        if not part:
            continue
        if SGR_TOKEN_RE.fullmatch(part):
            out.append(part)
            seen_sgr = True
        else:
            if rem <= 0:
                break
            chunk_chars: list[str] = []
            for ch in part:
                w = _char_display_width(ch)
                if rem - w < 0:
                    break
                chunk_chars.append(ch)
                rem -= w
            out.append("".join(chunk_chars))
    if seen_sgr:
        out.append("\033[0m")
    return "".join(out)


def render_viewport_frame(
    lines: Sequence[str],
    prompt: str,
    cols: int,
    rows: int,
) -> str:
    """Render a complete 2D terminal frame bounded strictly to `cols x rows` with prompt immediately below content."""
    safe_cols = max(40, cols)
    safe_rows = max(10, rows)
    body_budget = safe_rows - 1
    fitted_lines = list(lines[:body_budget])
    out: list[str] = ["\033[H\033[2J"]
    for idx, raw_line in enumerate(fitted_lines):
        row_num = idx + 1
        clipped = clip_visible(raw_line, safe_cols)
        out.append(f"\033[{row_num};1H\033[K{clipped}")
    prompt_row = min(safe_rows, len(fitted_lines) + 1)
    clipped_prompt = clip_visible(prompt, max(1, safe_cols - 1))
    out.append(f"\033[{prompt_row};1H\033[K{clipped_prompt}")
    return "".join(out)


def is_viewport_tty(stdout: Any = None) -> bool:
    """Return True when stdin and stdout are connected to an interactive terminal (not TERM=dumb)."""
    out = (
        stdout
        if stdout is not None
        else (sys.__stdout__ if sys.__stdout__ is not None else sys.stdout)
    )
    try:
        return bool(
            sys.stdin is not None
            and out is not None
            and sys.stdin.isatty()
            and out.isatty()
            and os.environ.get("TERM", "dumb") != "dumb"
        )
    except Exception:
        return False


def draw_bottom_prompt_line(
    prompt: str,
    buf_str: str,
    cursor_pos: int,
    cols: int,
    rows: int,
    prompt_row: int,
    stdout: Any = None,
) -> None:
    """Draw the prompt + line buffer clamped within `cols` at `prompt_row` without wrapping."""
    out = (
        stdout
        if stdout is not None
        else (sys.__stdout__ if sys.__stdout__ is not None else sys.stdout)
    )
    safe_cols = max(40, cols)
    safe_row = min(max(10, rows), max(1, prompt_row))
    p_clip = clip_visible(prompt, max(1, safe_cols - 2))
    p_vlen = visible_len(p_clip)
    avail = max(1, safe_cols - p_vlen - 1)
    if len(buf_str) <= avail:
        vis_buf = buf_str
        cur_offset = cursor_pos
    else:
        start = max(0, cursor_pos - avail + 1)
        vis_buf = buf_str[start : start + avail]
        cur_offset = cursor_pos - start
    target_col = min(safe_cols, p_vlen + cur_offset + 1)
    out.write(f"\033[{safe_row};1H\033[K{p_clip}{vis_buf}\033[{safe_row};{target_col}H")
    out.flush()


class ViewportSession:
    r"""Alternate-screen (\033[?1049h) context manager with termios preservation, SIGWINCH tracking, and RX queue."""

    def __init__(self, enabled: bool = True, stdout: Any = None) -> None:
        self.out = (
            stdout
            if stdout is not None
            else (sys.__stdout__ if sys.__stdout__ is not None else sys.stdout)
        )
        self.active = bool(enabled and is_viewport_tty(self.out))
        self.rx_buf = bytearray()
        self.winch_pending = False
        self.prompt_row = 1
        self._fd: int | None = None
        self._orig_termios: list[Any] | None = None
        self._prev_winch: Any = None

    def _on_sigwinch(self, _signum: int, _frame: Any) -> None:
        self.winch_pending = True

    def __enter__(self) -> ViewportSession:
        if not self.active:
            return self
        if termios is not None:
            try:
                self._fd = sys.stdin.fileno()
                self._orig_termios = termios.tcgetattr(self._fd)
                quiet_attrs = list(self._orig_termios)
                quiet_attrs[3] = quiet_attrs[3] & ~termios.ECHO
                termios.tcsetattr(self._fd, termios.TCSADRAIN, quiet_attrs)
            except Exception:
                self._fd = None
                self._orig_termios = None
        if hasattr(signal, "SIGWINCH"):
            try:
                self._prev_winch = signal.getsignal(signal.SIGWINCH)
                signal.signal(signal.SIGWINCH, self._on_sigwinch)
            except Exception:
                self._prev_winch = None
        self.out.write("\033[?1049h\033[?25h\033[H\033[2J")
        self.out.flush()
        return self

    def __exit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> bool:
        if not self.active:
            return False
        if (
            termios is not None
            and self._fd is not None
            and self._orig_termios is not None
        ):
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._orig_termios)
            except Exception:
                pass
        if self._prev_winch is not None and hasattr(signal, "SIGWINCH"):
            try:
                signal.signal(signal.SIGWINCH, self._prev_winch)
            except Exception:
                pass
        try:
            self.out.write("\033[r\033[0m\033[?25h\033[?1049l\033]0;\007")
            self.out.flush()
        except Exception:
            pass
        return False

    def write_frame(
        self, lines: Sequence[str], prompt: str, cols: int, rows: int
    ) -> int:
        """Render a viewport frame strictly bounded to `cols x rows` and record the active prompt row."""
        safe_rows = max(10, rows)
        fitted_count = min(len(lines), safe_rows - 1)
        self.prompt_row = min(safe_rows, fitted_count + 1)
        self.out.write(render_viewport_frame(lines, prompt, cols, rows))
        self.out.flush()
        return self.prompt_row

    def draw_prompt(
        self, prompt: str, buf_str: str, cursor_pos: int, cols: int, rows: int
    ) -> None:
        """Render the active prompt and input buffer on the bottom viewport row."""
        draw_bottom_prompt_line(
            prompt, buf_str, cursor_pos, cols, rows, self.prompt_row, stdout=self.out
        )

    def _next_byte(self, fd: int, timeout_s: float = 0.12) -> int | None:
        if self.rx_buf:
            return self.rx_buf.pop(0)
        try:
            rlist, _, _ = select.select([fd], [], [], timeout_s)
        except InterruptedError:
            return None
        if not rlist:
            return None
        try:
            chunk = os.read(fd, 1024)
        except (OSError, InterruptedError):
            return None
        if not chunk:
            return -1
        self.rx_buf.extend(chunk)
        return self.rx_buf.pop(0)

    def read_line(
        self,
        prompt: str,
        theme: ThemeEngine,
        *,
        redraw_fn: Callable[[str, int], None] | None = None,
        clear_fn: Callable[[str, int], None] | None = None,
        completer_fn: Callable[[str, int], tuple[str, int]] | None = None,
        history: Sequence[str] | None = None,
    ) -> str:
        """Read a line in the active viewport with cursor motion, history, Tab completion, Ctrl+L, and SIGWINCH redraw."""
        if not self.active or termios is None:
            self.out.write(prompt)
            self.out.flush()
            line = sys.stdin.readline()
            if not line:
                raise EOFError
            return line.rstrip("\r\n")

        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)
        new_attrs = list(old_attrs)
        new_attrs[3] = new_attrs[3] & ~(termios.ICANON | termios.ECHO | termios.ISIG)
        new_attrs[6] = list(old_attrs[6])
        new_attrs[6][termios.VMIN] = 1
        new_attrs[6][termios.VTIME] = 0

        buf: list[str] = []
        cursor_pos = 0
        hist_list = list(history) if history else []
        hist_idx = len(hist_list)
        saved_draft = ""
        cols, rows = theme.term_size()
        self.draw_prompt(prompt, "", 0, cols, rows)

        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, new_attrs)
            while True:
                if self.winch_pending:
                    self.winch_pending = False
                    cols, rows = theme.term_size()
                    if redraw_fn is not None:
                        redraw_fn("".join(buf), cursor_pos)
                    self.draw_prompt(prompt, "".join(buf), cursor_pos, cols, rows)

                b = self._next_byte(fd, timeout_s=0.12)
                if b is None:
                    continue
                if b == -1:
                    if not buf:
                        raise EOFError
                    return "".join(buf)
                if b in (10, 13):
                    if b == 13 and self.rx_buf and self.rx_buf[0] == 10:
                        self.rx_buf.pop(0)
                    return "".join(buf)
                if b == 3:
                    raise KeyboardInterrupt
                if b == 4:
                    if not buf:
                        raise EOFError
                    if cursor_pos < len(buf):
                        buf.pop(cursor_pos)
                        cols, rows = theme.term_size()
                        self.draw_prompt(prompt, "".join(buf), cursor_pos, cols, rows)
                    continue
                if b in (1, 5, 11, 21, 23):
                    if b == 1:
                        cursor_pos = 0
                    elif b == 5:
                        cursor_pos = len(buf)
                    elif b == 11:
                        del buf[cursor_pos:]
                    elif b == 21:
                        buf = buf[cursor_pos:]
                        cursor_pos = 0
                    elif b == 23:
                        i = cursor_pos
                        while i > 0 and buf[i - 1].isspace():
                            i -= 1
                        while i > 0 and not buf[i - 1].isspace():
                            i -= 1
                        del buf[i:cursor_pos]
                        cursor_pos = i
                    cols, rows = theme.term_size()
                    self.draw_prompt(prompt, "".join(buf), cursor_pos, cols, rows)
                    continue
                if b == 12:
                    cols, rows = theme.term_size()
                    if clear_fn is not None:
                        clear_fn("".join(buf), cursor_pos)
                    elif redraw_fn is not None:
                        redraw_fn("".join(buf), cursor_pos)
                    self.draw_prompt(prompt, "".join(buf), cursor_pos, cols, rows)
                    continue
                if b in (127, 8):
                    if cursor_pos > 0:
                        buf.pop(cursor_pos - 1)
                        cursor_pos -= 1
                        cols, rows = theme.term_size()
                        self.draw_prompt(prompt, "".join(buf), cursor_pos, cols, rows)
                    continue
                if b == 9:
                    if completer_fn is not None:
                        new_s, new_pos = completer_fn("".join(buf), cursor_pos)
                        buf = list(new_s)
                        cursor_pos = new_pos
                        cols, rows = theme.term_size()
                        self.draw_prompt(prompt, "".join(buf), cursor_pos, cols, rows)
                    continue
                if b == 27:
                    b1 = self._next_byte(fd, timeout_s=0.03)
                    if b1 in (ord("["), ord("O")):
                        b2 = self._next_byte(fd, timeout_s=0.03)
                        if b2 == ord("A") and hist_list and hist_idx > 0:
                            if hist_idx == len(hist_list):
                                saved_draft = "".join(buf)
                            hist_idx -= 1
                            buf = list(hist_list[hist_idx])
                            cursor_pos = len(buf)
                        elif b2 == ord("B") and hist_idx < len(hist_list):
                            hist_idx += 1
                            buf = list(
                                saved_draft
                                if hist_idx == len(hist_list)
                                else hist_list[hist_idx]
                            )
                            cursor_pos = len(buf)
                        elif b2 == ord("C") and cursor_pos < len(buf):
                            cursor_pos += 1
                        elif b2 == ord("D") and cursor_pos > 0:
                            cursor_pos -= 1
                        elif b2 == ord("H"):
                            cursor_pos = 0
                        elif b2 == ord("F"):
                            cursor_pos = len(buf)
                        elif b2 in (ord("1"), ord("3"), ord("4")):
                            _ = self._next_byte(fd, timeout_s=0.02)
                            if b2 == ord("1"):
                                cursor_pos = 0
                            elif b2 == ord("4"):
                                cursor_pos = len(buf)
                            elif cursor_pos < len(buf):
                                buf.pop(cursor_pos)
                        cols, rows = theme.term_size()
                        self.draw_prompt(prompt, "".join(buf), cursor_pos, cols, rows)
                    continue
                if b >= 32:
                    raw_bytes = bytearray([b])
                    if b >= 0xC0:
                        needed = 1 if b < 0xE0 else (2 if b < 0xF0 else 3)
                        for _ in range(needed):
                            nb = self._next_byte(fd, timeout_s=0.02)
                            if nb is not None and nb >= 0:
                                raw_bytes.append(nb)
                    ch = raw_bytes.decode("utf-8", errors="replace")
                    buf.insert(cursor_pos, ch)
                    cursor_pos += len(ch)
                    cols, rows = theme.term_size()
                    self.draw_prompt(prompt, "".join(buf), cursor_pos, cols, rows)
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            except Exception:
                pass

    def run_pager(
        self,
        title: str,
        lines: Sequence[str],
        header_fn: Callable[[int], list[str]],
        theme: ThemeEngine,
    ) -> None:
        """Scroll `lines` inside the viewport without pushing terminal scrollback."""
        expanded: list[str] = []
        for ln in lines:
            expanded.extend(str(ln).splitlines() or [""])
        if not expanded:
            expanded = ["(empty)"]
        if not self.active:
            for ln in expanded:
                print(ln)
            return

        offset = 0
        pager_prompt = theme.c("pager (Enter/k/g/G/q)> ", "primary", "bold")

        def _render(cur_buf: str = "", cur_pos: int = 0) -> tuple[int, int]:
            nonlocal offset
            cols, rows = theme.term_size()
            hdr = header_fn(cols)
            page_size = max(3, rows - len(hdr) - 2)
            max_offset = max(0, len(expanded) - page_size)
            offset = max(0, min(offset, max_offset))
            chunk = [
                clip_visible(ln, cols) for ln in expanded[offset : offset + page_size]
            ]
            footer = theme.c(
                clip_visible(
                    f"[{title}] {offset + 1}-{min(len(expanded), offset + page_size)}/{len(expanded)} | j/Enter=down, k=up, g/G, q=back",
                    cols,
                ),
                "secondary",
                "bold",
            )
            self.write_frame([*hdr, *chunk, footer], pager_prompt, cols, rows)
            if cur_buf:
                self.draw_prompt(pager_prompt, cur_buf, cur_pos, cols, rows)
            return page_size, max_offset

        while True:
            page_size, max_offset = _render()
            try:
                cmd_in = self.read_line(pager_prompt, theme, redraw_fn=_render).strip()
            except (EOFError, KeyboardInterrupt):
                break
            low = cmd_in.lower()
            if low in {"q", "quit", "exit", "back"}:
                break
            if low in {"k", "up", "p", "prev", "b"}:
                offset = max(0, offset - max(1, page_size // 2))
            elif low in {"g", "top", "home"}:
                offset = 0
            elif cmd_in == "G" or low in {"bottom", "end"}:
                offset = max_offset
            else:
                offset = min(max_offset, offset + max(1, page_size // 2))


def pad_visible(s: str, width: int, align: str = "left") -> str:
    """Pad string to target visible terminal column width."""
    vlen = visible_len(s)
    if vlen >= width:
        return s
    pad = " " * (width - vlen)
    if align == "right":
        return pad + s
    if align == "center":
        left = (width - vlen) // 2
        right = width - vlen - left
        return (" " * left) + s + (" " * right)
    return s + pad


class ThemeEngine:
    """Terminal styling, layout, and ANSI color rendering engine."""

    def __init__(self, theme_name: str | None = None):
        env_theme = os.environ.get("DT_THEME", "42-cluster")
        chosen = (theme_name or env_theme).lower()
        self.name = chosen
        self.palette = PALETTES.get(chosen, PALETTES["42-cluster"])
        self.enabled = (chosen != "plain") and (os.environ.get("NO_COLOR", "") == "")

    def c(self, text: str, role: str = "primary", *styles: str) -> str:
        """Apply semantic role and optional style escapes to text."""
        if not self.enabled:
            return str(text)
        role_map = {
            "primary": self.palette.primary,
            "secondary": self.palette.secondary,
            "info": self.palette.secondary,
            "accent": self.palette.cmd,
            "ok": self.palette.ok,
            "ko": self.palette.ko,
            "err": self.palette.ko,
            "warn": self.palette.warn,
            "purple": self.palette.purple,
            "muted": self.palette.muted,
            "border": self.palette.muted,
            "bold": self.palette.bold,
            "cmd": self.palette.cmd,
        }
        code = role_map.get(role, self.palette.primary)
        if "bold" in styles:
            if code == "\033[2m":
                code = "\033[1m"
            elif "\033[1m" not in code:
                code = f"\033[1m{code}"
        return f"{code}{text}{self.palette.reset}"

    def set_theme(self, theme_name: str) -> bool:
        """Switch active color palette by name; return True if found."""
        key = theme_name.lower().strip()
        if key in PALETTES:
            self.palette = PALETTES[key]
            self.name = key
            self.enabled = os.environ.get("NO_COLOR", "") == ""
            return True
        return False

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return str(text)
        return f"{code}{text}{self.palette.reset}"

    def primary(self, text: str) -> str:
        """Format text with primary palette style."""
        return self._wrap(self.palette.primary, text)

    def secondary(self, text: str) -> str:
        """Format text with secondary palette style."""
        return self._wrap(self.palette.secondary, text)

    def ok(self, text: str) -> str:
        """Format text with success/OK palette style."""
        return self._wrap(self.palette.ok, text)

    def ko(self, text: str) -> str:
        """Format text with failure/KO palette style."""
        return self._wrap(self.palette.ko, text)

    def warn(self, text: str) -> str:
        """Format text with warning palette style."""
        return self._wrap(self.palette.warn, text)

    def purple(self, text: str) -> str:
        """Format text with purple accent style."""
        return self._wrap(self.palette.purple, text)

    def muted(self, text: str) -> str:
        """Format text with muted/dim palette style."""
        return self._wrap(self.palette.muted, text)

    def bold(self, text: str) -> str:
        """Format text with bold palette style."""
        return self._wrap(self.palette.bold, text)

    def cmd(self, text: str) -> str:
        """Format text with command palette style."""
        return self._wrap(self.palette.cmd, text)

    def accent(self, text: str) -> str:
        """Format text with accent palette style."""
        return self._wrap(self.palette.cmd, text)

    def term_size(self) -> tuple[int, int]:
        """Return (cols, lines), honoring explicit COLUMNS/LINES before TTY size or (80, 24)."""
        env_c = os.environ.get("COLUMNS", "").strip()
        env_l = os.environ.get("LINES", "").strip()
        cols = int(env_c) if env_c.isdigit() and int(env_c) > 0 else 0
        lines = int(env_l) if env_l.isdigit() and int(env_l) > 0 else 0
        if cols <= 0 or lines <= 0:
            for stream in (sys.stdout, sys.stdin, sys.stderr):
                try:
                    if stream is not None and stream.isatty():
                        sz = os.get_terminal_size(stream.fileno())
                        cols = cols or sz.columns
                        lines = lines or sz.lines
                        break
                except OSError:
                    continue
        if cols <= 0 or lines <= 0:
            sz = shutil.get_terminal_size((80, 24))
            cols = cols or sz.columns
            lines = lines or sz.lines
        return max(40, cols), max(10, lines)

    def term_width(self, max_w: int = 92, min_w: int = 44) -> int:
        """Return clamped terminal width within [min_w, max_w]."""
        cols, _ = self.term_size()
        return max(min_w, min(cols, max_w))

    def startup_banner(
        self,
        version: str = "v0.1.1",
        mode: str = "real",
        width: int | None = None,
        height: int | None = None,
    ) -> str:
        """Render compact startup header line within terminal width bounds."""
        cols, _ = self.term_size()
        w = max(40, min(79, width if width is not None else cols))
        mode_tag = "practice" if mode == "practice" else "real"
        rule = self.c("=" * w, "border")
        title = self.c(f"examshell {version}", "primary", "bold")
        subtitle = self.c(
            f"42 / 1337 ({mode_tag}) | exam & grading harness",
            "secondary",
        )
        if w < 64:
            return "\n".join(
                [
                    rule,
                    clip_visible(f"{title} | 42 / 1337 ({mode_tag})", w),
                    clip_visible(self.c("exam & grading harness", "secondary"), w),
                    rule,
                ]
            )
        return "\n".join([rule, clip_visible(f"{title} | {subtitle}", w), rule])

    # ------------------------------------------------------------------
    # Classic 42 Bocal / ExamShell console status and table primitives
    # ('===' / '---' dividers, plain OK:/Error:/Warning: labels, and
    # clean aligned columns).
    # ------------------------------------------------------------------
    _STATUS_LABELS = {
        "status": ("", "secondary"),
        "good": ("OK:", "ok"),
        "error": ("Error:", "err"),
        "warning": ("Warning:", "warn"),
    }

    def status(self, kind: str, message: str) -> str:
        """Return a one-line message formatted in Classic 42 Bocal / ExamShell style."""
        label, role = self._STATUS_LABELS.get(kind, self._STATUS_LABELS["status"])
        if not label:
            return f"  {message}"
        body = message
        if body.lower().startswith(label.lower()):
            body = body[len(label) :].lstrip()
        return f"{self.c(label, role, 'bold')} {body}"

    def tool_banner(self, tool: str, width: int, tagline: str = "") -> list[str]:
        """42 emblem + tool wordmark (+ tagline), 7 rows x <=72 columns; empty when it cannot fit."""
        art = TOOL_WORDMARKS.get(tool)
        if not art or width < 72:
            return []
        offset = 1
        out: list[str] = []
        for i, left in enumerate(EMBLEM_42):
            j = i - offset
            if 0 <= j < len(art):
                right = self.c(art[j], "secondary", "bold")
            elif j == len(art) + 1 and tagline:
                right = self.c(clip_visible(tagline, width - 26), "muted")
            else:
                right = ""
            out.append((self.c(f"{left:<26}", "primary", "bold") + right).rstrip())
        return out

    def table(
        self,
        title: str,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        indent: int = 2,
        max_width: int = 79,
        highlight: Callable[[int, Sequence[str]], str | None] | None = None,
    ) -> list[str]:
        """Classic 42 Bocal / ExamShell table with '=' / '-' dividers and aligned columns."""
        w = max(40, min(79, max_width))
        widths = [visible_len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], visible_len(str(cell)))
        pad = " " * indent

        def _fmt(cells: Sequence[str]) -> str:
            parts = [pad_visible(str(c), widths[i]) for i, c in enumerate(cells)]
            return clip_visible((pad + "  ".join(parts)).rstrip(), w)

        out = [
            self.c("=" * w, "border"),
            clip_visible(f"{pad}{self.c(title, 'primary', 'bold')}", w),
            self.c("-" * w, "border"),
            self.c(_fmt(headers), "bold"),
            self.c(_fmt(["-" * widths[i] for i in range(len(headers))]), "border"),
        ]
        for r_idx, row in enumerate(rows):
            line = _fmt(row)
            role = highlight(r_idx, row) if highlight else None
            out.append(self.c(line, role) if role else line)
        return out

    def rule(self, label: str = "", width: int | None = None) -> str:
        """Render a horizontal divider line with an optional label."""
        w = width or self.term_width()
        if not label:
            return self.muted("─" * w)
        clean = f" {label.strip()} "
        rem = max(4, w - visible_len(clean) - 4)
        return self.muted("───") + self.secondary(clean) + self.muted("─" * rem)

    def progress_bar(
        self, current: float, total: float = 100.0, width: int = 16
    ) -> str:
        """Render an ASCII progress bar with percentage."""
        ratio = 0.0 if total <= 0 else max(0.0, min(1.0, current / total))
        filled = int(round(ratio * width))
        empty = max(0, width - filled)
        bar = "=" * filled + "-" * empty
        pct = int(round(ratio * 100))
        role = "ok" if pct >= 100 else ("warn" if pct >= 50 else "ko")
        return f"[{self.c(bar, role)}] {pct}%"

    def banner(self, title: str, subtitle: str = "", badge: str = "1337 / 42") -> str:
        """Render a section header with optional subtitle."""
        out = [f"{self.c('===>', 'accent', 'bold')} {self.bold(title)}"]
        if subtitle:
            out.append(self.c(f"     {subtitle}", "muted"))
        return "\n".join(out)

    def box_panel(
        self, title: str, body_lines: Sequence[str], border_color: str = "muted"
    ) -> str:
        """Render titled indented content lines."""
        out: list[str] = []
        if title:
            out.append(f"{self.c('===>', 'accent', 'bold')} {self.bold(title)}")
        for raw_line in body_lines:
            for sub in raw_line.splitlines() or [""]:
                out.append(f"     {sub}" if title else sub)
        return "\n".join(out)

    def render_subject(
        self, subject_text: str, subject_id: str = "", full: bool = False
    ) -> str:
        """Format exercise subject text with highlighted headers and examples."""
        raw_lines = subject_text.splitlines()
        lines: list[str] = []
        for line in raw_lines:
            if (
                not full
                and line.startswith(">>> ")
                and (
                    "TEST" in line
                    or "EDGE CASE" in line
                    or "ORACLE" in line
                    or "DEDICATED" in line
                )
            ):
                break
            lines.append(line)
        while lines and not lines[-1].strip():
            lines.pop()

        styled: list[str] = []
        in_header = True
        for line in lines:
            if line.startswith("----"):
                in_header = False
                styled.append(self.muted("─" * (self.term_width() - 6)))
                continue
            if in_header and ":" in line:
                k, v = line.split(":", 1)
                k_clean = k.strip()
                v_clean = v.strip()
                if "Allowed" in k_clean:
                    v_colored = (
                        self.ok(v_clean)
                        if v_clean.lower() not in {"none", "-", ""}
                        else self.warn(v_clean or "None")
                    )
                elif "Expected" in k_clean or "Files" in k_clean:
                    v_colored = self.cmd(v_clean)
                else:
                    v_colored = self.bold(v_clean)
                styled.append(f"{self.secondary(f'{k_clean:<18}')} : {v_colored}")
            elif line.lstrip().startswith("$>"):
                styled.append(self.cmd(line))
            elif (
                line.startswith("Examples:")
                or line.startswith("Example:")
                or line.startswith("Exemples:")
            ):
                styled.append(self.warn(line))
            elif line.endswith("$") or line.endswith("$>"):
                styled.append(self.ok(line))
            else:
                styled.append(line)
        return self.box_panel(
            f"SUBJECT — {subject_id or '42 Assignment'}", styled, border_color="primary"
        )

    def colorize_trace(self, trace_text: str) -> str:
        """Apply diff and status colors to a grading trace."""
        out: list[str] = []
        for line in trace_text.splitlines():
            if line.startswith("= ") and line.endswith("="):
                out.append(self.primary(line))
            elif line.startswith("$> "):
                out.append(self.cmd(line))
            elif line.startswith("--- "):
                out.append(self.ko(line))
            elif line.startswith("+++ "):
                out.append(self.ok(line))
            elif line.startswith("@@ "):
                out.append(self.secondary(line))
            elif line.startswith("-"):
                out.append(self.ko(line))
            elif line.startswith("+"):
                out.append(self.ok(line))
            elif "Diff OK :D" in line or "Final grade: 100" in line or "OK :)" in line:
                out.append(self.ok(line))
            elif any(
                tok in line
                for tok in (
                    "Diff KO :(",
                    "Does not compile",
                    "Cheating (-42)",
                    "Grade: 0",
                    "Grade: -42",
                    "Timeout",
                    "Segmentation fault",
                    "Norme error",
                    "Nothing turned in",
                )
            ):
                out.append(self.ko(line))
            elif line.startswith("[Moulinette") or line.startswith("[Strict Mode"):
                out.append(self.warn(line))
            else:
                out.append(line)
        return "\n".join(out)

    def colorize_code(self, code_text: str, show_lineno: bool = True) -> str:
        """Apply lightweight C syntax highlighting and optional line numbers."""
        out: list[str] = []
        in_block_comment = False
        token_re = re.compile(
            r"(?P<comment>//.*|/\*[\s\S]*?\*/)"
            r'|(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
            r"|\b(?P<kw>if|else|while|for|return|break|continue|typedef|struct|enum|union|static|const|unsigned|signed|void|int|char|long|short|size_t|ssize_t)\b"
        )
        for idx, line in enumerate(code_text.splitlines(), 1):
            num_prefix = f"{self.muted(f'{idx:3d} │')} " if show_lineno else "  "
            stripped = line.strip()
            if in_block_comment:
                out.append(num_prefix + self.muted(line))
                if "*/" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("/*") and not (
                "*/" in stripped and stripped.index("*/") > 1
            ):
                in_block_comment = True
                out.append(num_prefix + self.muted(line))
                continue
            if stripped.startswith("/*") and stripped.endswith("*/"):
                out.append(num_prefix + self.muted(line))
                continue
            if stripped.startswith("//") or (
                stripped.startswith("#")
                and not stripped.startswith("#include")
                and not stripped.startswith("#define")
                and not stripped.startswith("#ifndef")
                and not stripped.startswith("#endif")
            ):
                out.append(num_prefix + self.muted(line))
                continue
            if stripped.startswith("#"):
                out.append(num_prefix + self.purple(line))
                continue
            if not self.enabled:
                out.append(num_prefix + line)
                continue

            def _repl(m: re.Match[str]) -> str:
                if m.group("comment"):
                    return (
                        f"{self.palette.muted}{m.group('comment')}{self.palette.reset}"
                    )
                if m.group("string"):
                    return f"{self.palette.warn}{m.group('string')}{self.palette.reset}"
                if m.group("kw"):
                    return (
                        f"{self.palette.secondary}{m.group('kw')}{self.palette.reset}"
                    )
                return m.group(0)

            colored_line = token_re.sub(_repl, line)
            out.append(num_prefix + colored_line)
        return "\n".join(out)

    def render_pro_hint(
        self,
        kit_root: os.PathLike | str,
        subject_rel: str,
        mode: str = "1",
        turnin_dir: os.PathLike | str | None = None,
    ) -> str:
        """Hints and reference solutions are locked; every mode returns the same refusal."""
        return self.status(
            "error",
            "Reference solutions and hints are strictly locked. Use 'subject <ex>' and debug from the Deepthought trace.",
        )

    def scorecard_table(
        self, title: str, headers: Sequence[str], rows: Sequence[Sequence[str]]
    ) -> str:
        """Render an aligned plain/ANSI table for scorecards."""
        if not headers:
            return ""
        col_count = len(headers)
        col_widths = [visible_len(h) for h in headers]
        for r in rows:
            for idx, cell in enumerate(r):
                if idx < col_count:
                    col_widths[idx] = max(col_widths[idx], visible_len(str(cell)))

        out = []
        if title:
            out.append(f"{self.c('===>', 'accent', 'bold')} {self.bold(title)}")
        hdr_cells = [
            pad_visible(self.c(str(h).upper(), "muted"), col_widths[i])
            for i, h in enumerate(headers)
        ]
        sep_cells = [self.c("-" * col_widths[i], "muted") for i in range(col_count)]
        out.append("  " + "  ".join(hdr_cells).rstrip())
        out.append("  " + "  ".join(sep_cells).rstrip())
        for r in rows:
            cells = []
            for i in range(col_count):
                val = str(r[i]) if i < len(r) else ""
                cells.append(
                    pad_visible(val, col_widths[i]) if i < col_count - 1 else val
                )
            out.append("  " + "  ".join(cells).rstrip())
        return "\n".join(out)
