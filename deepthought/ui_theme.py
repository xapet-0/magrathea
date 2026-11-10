"""
deepthought.ui_theme
Authentic 24-bit / 256-color ANSI & Unicode Terminal UI Engine for 1337 / 42 Deepthought Kit.
Combines visual design patterns from:
- JCluzet/42_EXAM (VIP status header, live grading progression, cheat/practice toggles)
- wkratos/42-examshell (Interactive track selector, timer & cooldown progress bars)
- k11q/mini-moulinette (Module scorecard tables, syntax-colored unified diffs)
- piscine_forge/rich_ui.py & theme.py (4 selectable cluster themes: 42-cluster, jcluzet-exam, tokyo-night, gruvbox)
"""
from __future__ import annotations

import fcntl
import os
import re
import shlex
import shutil
import struct
import sys
import termios
from dataclasses import dataclass
from typing import Callable, Sequence


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
    name: str
    primary: str      # Main frame / brand accent
    secondary: str    # Headers / keys
    ok: str           # Moulinette OK / diff +
    ko: str           # Moulinette KO / diff -
    warn: str         # Cooldown / timer / warnings
    purple: str       # Oracle / VIP badge
    muted: str        # Borders / subtle text
    bold: str         # Bright white bold
    cmd: str          # Shell commands `$> ...`
    reset: str = "\033[0m"


PALETTES: dict[str, ColorPalette] = {
    "42-cluster": ColorPalette(
        name="42-cluster",
        primary="\033[1m",           # Bold white
        secondary="\033[2m",         # Dim / muted
        ok="\033[32m",               # Standard green
        ko="\033[31m",               # Standard red
        warn="\033[33m",             # Standard yellow
        purple="\033[35m",           # Standard magenta
        muted="\033[2m",             # Dim
        bold="\033[1m",              # Bold
        cmd="\033[36m",              # Cyan
    ),
    "jcluzet-exam": ColorPalette(
        name="jcluzet-exam",
        primary="\033[38;2;0;255;135m",      # #00FF87 Neon Exam Green
        secondary="\033[38;2;0;215;255m",    # #00D7FF Electric Cyan
        ok="\033[1;38;2;0;255;135m",
        ko="\033[1;38;2;255;59;92m",         # #FF3B5C High-Contrast Red
        warn="\033[1;38;2;255;214;10m",      # #FFD60A Gold
        purple="\033[1;38;2;215;95;255m",    # #D75FFF VIP Magenta
        muted="\033[38;2;120;130;145m",
        bold="\033[1;97m",
        cmd="\033[38;2;255;214;10m",
    ),
    "tokyo-night": ColorPalette(
        name="tokyo-night",
        primary="\033[38;2;122;162;247m",    # #7AA2F7
        secondary="\033[38;2;125;207;255m",  # #7DCFFF
        ok="\033[38;2;158;206;106m",         # #9ECE6A
        ko="\033[38;2;247;118;142m",         # #F7768E
        warn="\033[38;2;224;175;104m",       # #E0AF68
        purple="\033[38;2;187;154;247m",     # #BB9AF7
        muted="\033[38;2;86;95;137m",        # #565F89
        bold="\033[1;38;2;192;202;245m",
        cmd="\033[38;2;125;207;255m",
    ),
    "gruvbox": ColorPalette(
        name="gruvbox",
        primary="\033[38;2;250;189;47m",     # #FABD2F
        secondary="\033[38;2;131;165;152m",  # #83A598
        ok="\033[38;2;184;187;38m",          # #B8BB26
        ko="\033[38;2;251;73;52m",           # #FB4934
        warn="\033[38;2;254;128;25m",        # #FE8019
        purple="\033[38;2;211;134;155m",     # #D3869B
        muted="\033[38;2;146;131;116m",      # #928374
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


def pad_visible(s: str, width: int, align: str = "left") -> str:
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
    def __init__(self, theme_name: str | None = None):
        env_theme = os.environ.get("DT_THEME", "42-cluster")
        chosen = (theme_name or env_theme).lower()
        self.name = chosen
        self.palette = PALETTES.get(chosen, PALETTES["42-cluster"])
        self.enabled = (chosen != "plain") and (os.environ.get("NO_COLOR", "") == "")

    def c(self, text: str, role: str = "primary", *styles: str) -> str:
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
        key = theme_name.lower().strip()
        if key in PALETTES:
            self.palette = PALETTES[key]
            return True
        return False

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return str(text)
        return f"{code}{text}{self.palette.reset}"

    def primary(self, text: str) -> str:
        return self._wrap(self.palette.primary, text)

    def secondary(self, text: str) -> str:
        return self._wrap(self.palette.secondary, text)

    def ok(self, text: str) -> str:
        return self._wrap(self.palette.ok, text)

    def ko(self, text: str) -> str:
        return self._wrap(self.palette.ko, text)

    def warn(self, text: str) -> str:
        return self._wrap(self.palette.warn, text)

    def purple(self, text: str) -> str:
        return self._wrap(self.palette.purple, text)

    def muted(self, text: str) -> str:
        return self._wrap(self.palette.muted, text)

    def bold(self, text: str) -> str:
        return self._wrap(self.palette.bold, text)

    def cmd(self, text: str) -> str:
        return self._wrap(self.palette.cmd, text)

    def accent(self, text: str) -> str:
        return self._wrap(self.palette.cmd, text)

    def term_size(self) -> tuple[int, int]:
        cols, lines = 0, 0
        for stream in (sys.stdout, sys.stdin, sys.stderr):
            try:
                if stream is not None and stream.isatty():
                    packed = fcntl.ioctl(stream.fileno(), termios.TIOCGWINSZ, b"\x00" * 8)
                    r_ioctl, c_ioctl, _, _ = struct.unpack("HHHH", packed)
                    if c_ioctl > 0 and r_ioctl > 0:
                        cols, lines = int(c_ioctl), int(r_ioctl)
                        break
            except Exception:
                continue
        if cols <= 0 or lines <= 0:
            env_cols = os.environ.get("COLUMNS", "").strip()
            env_lines = os.environ.get("LINES", "").strip()
            if env_cols.isdigit() and int(env_cols) > 0:
                cols = int(env_cols)
            if env_lines.isdigit() and int(env_lines) > 0:
                lines = int(env_lines)
        if cols <= 0 or lines <= 0:
            try:
                sz = shutil.get_terminal_size((80, 24))
                if cols <= 0:
                    cols = sz.columns
                if lines <= 0:
                    lines = sz.lines
            except OSError:
                if cols <= 0:
                    cols = 80
                if lines <= 0:
                    lines = 24
        return max(40, cols), max(10, lines)

    def term_width(self, max_w: int = 92, min_w: int = 44) -> int:
        cols, _ = self.term_size()
        return max(min_w, min(cols, max_w))

    def startup_banner(
        self,
        version: str = "v0.1.1",
        mode: str = "real",
        width: int | None = None,
        height: int | None = None,
    ) -> str:
        cols, _ = self.term_size()
        w = max(40, min(80, width if width is not None else cols))
        mode_tag = "practice" if mode == "practice" else "real"
        rule = self.c("=" * w, "border")
        title = self.c(f"examshell {version}", "primary", "bold")
        subtitle = self.c(
            f"42/1337 ({mode_tag}) | MAGRATHEA - Don't Panic.",
            "secondary",
        )
        if w < 64:
            return "\n".join([rule, clip_visible(f"{title} | 42/1337 ({mode_tag})", w), clip_visible(self.c("MAGRATHEA — Don't Panic.", "secondary"), w), rule])
        return "\n".join([rule, clip_visible(f"{title} | {subtitle}", w), rule])

    # ------------------------------------------------------------------
    # Console primitives modelled on msfconsole's UX conventions
    # (status glyphs, "=[ ]=" stats block, Rex-style tables). Patterns
    # only; no Metasploit source is reproduced here.
    # ------------------------------------------------------------------
    _GLYPHS = {
        "status": ("[*]", "secondary"),
        "good": ("[+]", "ok"),
        "error": ("[-]", "err"),
        "warning": ("[!]", "warn"),
    }

    def status(self, kind: str, message: str) -> str:
        """Return a one-line message prefixed with an msfconsole-style glyph ([*] [+] [-] [!])."""
        glyph, role = self._GLYPHS.get(kind, self._GLYPHS["status"])
        return f"{self.c(glyph, role, 'bold')} {message}"

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

    def stats_block(self, lines: Sequence[str], width: int = 66) -> list[str]:
        """msfconsole-style summary block:  '       =[ text ]' then '+ -- --=[ text ]'."""
        inner = max(20, min(width, 80) - 14)
        out: list[str] = []
        for idx, raw in enumerate(lines):
            lead = "       =[ " if idx == 0 else "+ -- --=[ "
            body = clip_visible(raw, inner)
            body = body + " " * max(0, inner - visible_len(body))
            out.append(self.c(lead, "border") + body + self.c(" ]", "border"))
        return out

    def table(
        self,
        title: str,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        indent: int = 3,
        max_width: int = 80,
        highlight: Callable[[int, Sequence[str]], str | None] | None = None,
    ) -> list[str]:
        """Rex-style table: title, '=' underline, blank, header, '-' underline per column, rows."""
        widths = [visible_len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], visible_len(str(cell)))
        pad = " " * indent

        def _fmt(cells: Sequence[str]) -> str:
            parts = [pad_visible(str(c), widths[i]) for i, c in enumerate(cells)]
            return clip_visible((pad + "  ".join(parts)).rstrip(), max_width)

        out = [self.c(title, "primary", "bold"), self.c("=" * visible_len(title), "border"), ""]
        out.append(self.c(_fmt(headers), "bold"))
        out.append(self.c(_fmt(["-" * visible_len(h) for h in headers]), "border"))
        for r_idx, row in enumerate(rows):
            line = _fmt(row)
            role = highlight(r_idx, row) if highlight else None
            out.append(self.c(line, role) if role else line)
        return out

    def rule(self, label: str = "", width: int | None = None) -> str:
        w = width or self.term_width()
        if not label:
            return self.muted("─" * w)
        clean = f" {label.strip()} "
        rem = max(4, w - visible_len(clean) - 4)
        return self.muted("───") + self.secondary(clean) + self.muted("─" * rem)

    def progress_bar(self, current: float, total: float = 100.0, width: int = 16) -> str:
        ratio = 0.0 if total <= 0 else max(0.0, min(1.0, current / total))
        filled = int(round(ratio * width))
        empty = max(0, width - filled)
        bar = "=" * filled + "-" * empty
        pct = int(round(ratio * 100))
        role = "ok" if pct >= 100 else ("warn" if pct >= 50 else "ko")
        return f"[{self.c(bar, role)}] {pct}%"

    def banner(self, title: str, subtitle: str = "", badge: str = "1337 / 42") -> str:
        out = [f"{self.c('===>', 'accent', 'bold')} {self.bold(title)}"]
        if subtitle:
            out.append(self.c(f"     {subtitle}", "muted"))
        return "\n".join(out)

    def box_panel(self, title: str, body_lines: Sequence[str], border_color: str = "muted") -> str:
        out: list[str] = []
        if title:
            out.append(f"{self.c('===>', 'accent', 'bold')} {self.bold(title)}")
        for raw_line in body_lines:
            for sub in (raw_line.splitlines() or [""]):
                out.append(f"     {sub}" if title else sub)
        return "\n".join(out)

    def render_subject(self, subject_text: str, subject_id: str = "", full: bool = False) -> str:
        raw_lines = subject_text.splitlines()
        lines: list[str] = []
        truncated_extra = False
        for line in raw_lines:
            if not full and line.startswith(">>> ") and ("TEST" in line or "EDGE CASE" in line or "ORACLE" in line or "DEDICATED" in line):
                truncated_extra = True
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
                    v_colored = self.ok(v_clean) if v_clean.lower() not in {"none", "-", ""} else self.warn(v_clean or "None")
                elif "Expected" in k_clean or "Files" in k_clean:
                    v_colored = self.cmd(v_clean)
                else:
                    v_colored = self.bold(v_clean)
                styled.append(f"{self.secondary(f'{k_clean:<18}')} : {v_colored}")
            elif line.lstrip().startswith("$>"):
                styled.append(self.cmd(line))
            elif line.startswith("Examples:") or line.startswith("Example:") or line.startswith("Exemples:"):
                styled.append(self.warn(line))
            elif line.endswith("$") or line.endswith("$>"):
                styled.append(self.ok(line))
            else:
                styled.append(line)
        if truncated_extra:
            styled.append("")
            styled.append(self.muted("─" * (self.term_width() - 6)))
            styled.append(self.secondary("Tip: Run `subject --full` to inspect the full specification."))
        return self.box_panel(f"SUBJECT — {subject_id or '42 Assignment'}", styled, border_color="primary")

    def colorize_trace(self, trace_text: str) -> str:
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
            elif any(tok in line for tok in ("Diff KO :(", "Does not compile", "Cheating (-42)", "Grade: 0", "Grade: -42", "Timeout", "Segmentation fault", "Norme error", "Nothing turned in")):
                out.append(self.ko(line))
            elif line.startswith("[Moulinette") or line.startswith("[Strict Mode"):
                out.append(self.warn(line))
            else:
                out.append(line)
        return "\n".join(out)

    def colorize_code(self, code_text: str, show_lineno: bool = True) -> str:
        out: list[str] = []
        in_block_comment = False
        token_re = re.compile(
            r'(?P<comment>//.*|/\*[\s\S]*?\*/)'
            r'|(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
            r'|\b(?P<kw>if|else|while|for|return|break|continue|typedef|struct|enum|union|static|const|unsigned|signed|void|int|char|long|short|size_t|ssize_t)\b'
        )
        for idx, line in enumerate(code_text.splitlines(), 1):
            num_prefix = f"{self.muted(f'{idx:3d} │')} " if show_lineno else "  "
            stripped = line.strip()
            if in_block_comment:
                out.append(num_prefix + self.muted(line))
                if "*/" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("/*") and not ("*/" in stripped and stripped.index("*/") > 1):
                in_block_comment = True
                out.append(num_prefix + self.muted(line))
                continue
            if stripped.startswith("/*") and stripped.endswith("*/"):
                out.append(num_prefix + self.muted(line))
                continue
            if stripped.startswith("//") or (stripped.startswith("#") and not stripped.startswith("#include") and not stripped.startswith("#define") and not stripped.startswith("#ifndef") and not stripped.startswith("#endif")):
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
                    return f"{self.palette.muted}{m.group('comment')}{self.palette.reset}"
                if m.group("string"):
                    return f"{self.palette.warn}{m.group('string')}{self.palette.reset}"
                if m.group("kw"):
                    return f"{self.palette.secondary}{m.group('kw')}{self.palette.reset}"
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
        from pathlib import Path
        import yaml

        root = Path(kit_root)
        subj_dir = root / "subjects" / subject_rel
        slug = subj_dir.name
        mode_key = (mode or "1").strip().lower()

        if mode_key in {"4", "solution", "solve", "--solution", "--solve"}:
            return self.status(
                "error",
                "Reference solutions and hints are strictly locked. Use 'subject <ex>' and debug from the Deepthought trace.",
            )
        return self.status(
            "error",
            "Reference solutions and hints are strictly locked. Use 'subject <ex>' and debug from the Deepthought trace.",
        )

        meta_path = subj_dir / "meta.yml"
        tests_path = subj_dir / "tests.yml"
        subj_txt_path = subj_dir / "subject.en.txt"

        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        tests_data = yaml.safe_load(tests_path.read_text(encoding="utf-8")) if tests_path.is_file() else {}
        subj_txt = subj_txt_path.read_text(encoding="utf-8", errors="ignore") if subj_txt_path.is_file() else ""

        stype = str(meta.get("type") or tests_data.get("mode") or "c_program")
        exp_files = meta.get("expected_files") or [f"{slug}.c"]
        allowed = meta.get("allowed_functions") or []
        proto = str(meta.get("prototype") or "None (Program / Script)")
        xp = meta.get("xp", 100)
        module_name = meta.get("module", subject_rel)

        # Build Contract Section
        if stype == "c_function":
            mode_badge = self.warn("C FUNCTION ONLY — Do NOT include main() in your submitted file!")
        elif stype == "c_program":
            mode_badge = self.ok("C PROGRAM — Must define int main(int argc, char **argv) and return 0")
        elif stype in {"shell", "shell_script"}:
            mode_badge = self.cmd("POSIX SHELL SCRIPT — Must pass shnorm and execute cleanly under /bin/sh")
        elif stype == "header":
            mode_badge = self.purple("C HEADER FILE — Include #ifndef / #define / #endif double-inclusion guards")
        else:
            mode_badge = self.secondary(stype.upper())

        allow_str = ", ".join(str(a) for a in allowed) if allowed else "None (only language built-ins)"
        contract_lines = [
            f"{self.secondary('Exercise         ')}: {self.bold(slug)}  {self.muted(f'({module_name} • {xp} XP)')}",
            f"{self.secondary('Submission Mode  ')}: {mode_badge}",
            f"{self.secondary('Expected Files   ')}: {self.cmd(', '.join(str(f) for f in exp_files))}",
            f"{self.secondary('Allowed Functions')}: {self.ok(allow_str) if allowed else self.warn(allow_str)}",
            f"{self.secondary('Prototype        ')}: {self.bold(proto)}",
        ]
        if turnin_dir:
            contract_lines.append(f"{self.secondary('Turn-in Folder   ')}: {self.cmd(str(turnin_dir))}")

        # Build Step-by-Step Algorithm & Moulinette Traps
        algo_steps: list[str] = []
        traps: list[str] = []

        fixed_tests = tests_data.get("fixed_tests") or []
        subj_examples = tests_data.get("subject_examples") or []

        if stype == "c_program":
            # Analyze argc handling from fixed_tests & subject examples
            no_arg_tests = [ft for ft in fixed_tests if ft.get("args") == []]
            one_arg_tests = [ft for ft in fixed_tests if len(ft.get("args") or []) == 1]
            multi_arg_tests = [ft for ft in fixed_tests if len(ft.get("args") or []) > 1]

            if one_arg_tests and not multi_arg_tests:
                algo_steps.append("1. Argument Check: Verify `if (argc == 2)` before processing `argv[1]`. If `argc != 2`, write `\"\\n\"` and return `0`.")
            elif multi_arg_tests and all(len(ft.get("args") or []) == 2 for ft in multi_arg_tests):
                algo_steps.append("1. Argument Check: Verify `if (argc == 3)` to process `argv[1]` and `argv[2]`. Otherwise output `\"\\n\"` and return `0`.")
            elif multi_arg_tests:
                algo_steps.append("1. Argument Loop: Check `if (argc > 1)` (or iterate `i = 1` to `argc - 1`). When no arguments are passed (`argc == 1`), output `\"\\n\"`.")
            elif no_arg_tests and not one_arg_tests and not multi_arg_tests:
                algo_steps.append("1. Entry Point: This program ignores command-line arguments (`(void)argc; (void)argv;`) and outputs a fixed result.")
            else:
                algo_steps.append("1. Entry Point: Check `argc` against the subject requirements before accessing `argv[1]`.")

            if "write" in allowed and "printf" not in allowed:
                algo_steps.append("2. Output System Call: Include `<unistd.h>` and use `write(1, ..., ...)` for all output (`printf`/`puts` are FORBIDDEN).")
                traps.append(f"{self.ko('[TRAP — Forbidden Functions]')} Only `{allow_str}` allowed. Using `printf`, `strlen`, or `putchar` triggers `Cheating (-42)`.")
            if "malloc" in allowed:
                algo_steps.append("3. Dynamic Memory: Include `<stdlib.h>`, check `if (!ptr)` after every `malloc`, and `free()` before exiting.")

            # Check newline behavior on first test
            if fixed_tests:
                first_exp = str(fixed_tests[0].get("expected") if fixed_tests[0].get("expected") is not None else fixed_tests[0].get("stdout", ""))
                if first_exp and not first_exp.endswith("\n"):
                    traps.append(f"{self.warn('[TRAP — NO Trailing Newline]')} Expected output `{first_exp!r}` does NOT end with `'\\n'`! Do not print an extra newline.")
                elif first_exp.endswith("\n"):
                    traps.append(f"{self.ok('[TRAP — Trailing Newline]')} Every output must end with `'\\n'` (`$` in `cat -e`).")
            if no_arg_tests:
                no_arg_exp = str(no_arg_tests[0].get("expected", ""))
                traps.append(f"{self.warn('[TRAP — Zero Arguments (`argc == 1`)]')} Running with no arguments expects `{no_arg_exp.encode('unicode_escape').decode()}`.")
            if multi_arg_tests:
                m_args = multi_arg_tests[0].get("args")
                m_exp = str(multi_arg_tests[0].get("expected", ""))
                traps.append(f"{self.warn(f'[TRAP — Multiple Arguments (`argc == {len(m_args) + 1}`)]')} Passing `{m_args}` expects `{m_exp.encode('unicode_escape').decode()}`.")

        elif stype == "c_function":
            algo_steps.append(f"1. Exact Function Signature: Implement `{proto}` inside `{exp_files[0]}`.")
            algo_steps.append("2. No `main()` Function: Moulinette links its own `__dt_main.c` test driver. Remove or comment out your test `main()` before grading!")
            if "malloc" in allowed:
                algo_steps.append("3. Heap Allocation & Null Guard: Include `<stdlib.h>`, allocate the exact size (+1 for `'\\0'` or `NULL` terminator), and return `NULL` if `malloc` fails.")
                traps.append(f"{self.ko('[TRAP — Unchecked malloc]')} Strict mode injects `malloc() -> NULL`. Always check `if (!res) return (NULL);` immediately.")
            if "int " in proto and ("atoi" in slug or "putnbr" in slug or "itoa" in slug):
                traps.append(f"{self.warn('[TRAP — INT_MIN Overflow]')} Handle `-2147483648` (`INT_MIN`) by promoting `int n` to `long nb = n;` before negating `nb = -nb`.")
            if "char *" in proto and ("cmp" in slug or "str" in slug):
                traps.append(f"{self.warn('[TRAP — Unsigned Char & Null Terminator]')} Always stop at `'\\0'` and cast characters to `(unsigned char)` when comparing.")
            traps.append(f"{self.ko('[TRAP — Leftover main()]')} Leaving `int main(...)` in `{exp_files[0]}` causes an immediate Gate 1 failure.")
            if not allowed:
                traps.append(f"{self.ko('[TRAP — External Functions]')} Allowed functions: `None`. Do not call `strlen`, `malloc`, or `printf` inside `{slug}`.")

        elif stype in {"shell", "shell_script"}:
            algo_steps.append("1. Shebang: Start the file with `#!/bin/sh` on line 1 (no leading spaces).")
            algo_steps.append("2. Formatting: Keep lines under 80 chars, quote shell variables (`\"$VAR\"`), and use 4 spaces for indentation (`shnorm`).")
            traps.append(f"{self.warn('[TRAP — shnorm Compliance]')} Run `./bin/shnorm` on your script to verify 42 shell norm rules.")

        # Build Test Cases Preview (Tier 2)
        test_lines: list[str] = []
        sample_pool = fixed_tests[:6]
        for idx, ft in enumerate(sample_pool, 1):
            t_desc = ft.get("description") or ft.get("name") or f"Test {idx}"
            if "args" in ft:
                args_str = " ".join(shlex.quote(str(a)) for a in (ft.get("args") or []))
                inv = f"$> ./{slug} {args_str}".rstrip() + " | cat -e"
            elif "call" in ft:
                inv = str(ft["call"]).replace(r"\|", "|")
            elif "expr" in ft:
                inv = str(ft["expr"]).replace(r"\|", "|")
            elif "code" in ft:
                inv = str(ft["code"]).replace(r"\|", "|")
            else:
                inv = f"eval {slug}"
            raw_exp = str(ft.get("expected") if ft.get("expected") is not None else ft.get("stdout", ""))
            cat_e_single = raw_exp.replace("\n", "$\\n")
            if cat_e_single.endswith("$\\n"):
                cat_e_single = cat_e_single[:-2]
            if len(cat_e_single) > 68:
                cat_e_single = cat_e_single[:65] + "..."
            test_lines.append(f"  {self.bold(f'[{idx}]')} {self.secondary(t_desc)}")
            test_lines.append(f"      {self.muted('Run     :')} {self.cmd(inv)}")
            test_lines.append(f"      {self.muted('Expect  :')} {self.ok(cat_e_single)}")

        # Build Skeleton (Tier 3) purely from subject metadata (never reading corrections/)
        skeleton_lines: list[str] = []
        if stype in {"c_program", "c_function"}:
            if any(f in allowed for f in ("write", "read", "close")):
                skeleton_lines.append("#include <unistd.h>")
            if any(f in allowed for f in ("malloc", "free", "exit")):
                skeleton_lines.append("#include <stdlib.h>")
            if skeleton_lines:
                skeleton_lines.append("")
            if stype == "c_function" and proto and "None" not in proto and "main(" not in proto:
                skeleton_lines.append(proto.rstrip(";"))
                skeleton_lines.append("{")
                skeleton_lines.append(f"    /* TODO: implement {slug} step-by-step */")
                skeleton_lines.append("}")
            else:
                skeleton_lines.append("int main(int argc, char **argv)")
                skeleton_lines.append("{")
                skeleton_lines.append("    /* 1. Validate argc / argv */")
                skeleton_lines.append("    /* 2. Call helper logic & output with write() */")
                skeleton_lines.append("    (void)argc;")
                skeleton_lines.append("    (void)argv;")
                skeleton_lines.append("    return (0);")
                skeleton_lines.append("}")
        else:
            skeleton_lines.append(f"/* Starter template for {slug} ({', '.join(str(f) for f in exp_files)}) */")

        panels: list[str] = []
        panels.append(self.box_panel(f"MOULINETTE PRO HINT & COACH — {slug.upper()}", contract_lines, border_color="primary"))

        if mode_key in {"1", "algo", "traps", "overview", "all", "full", ""}:
            body_1: list[str] = [self.bold("Step-by-Step Strategy:")]
            for s in algo_steps:
                body_1.append(f"  • {s}")
            if traps:
                body_1.append("")
                body_1.append(self.bold("Moulinette Trap Checklist:"))
                for tr in traps:
                    body_1.append(f"  • {tr}")
            panels.append(self.box_panel("TIER 1 — STRATEGY & MOULINETTE TRAPS", body_1, border_color="warn"))

        if mode_key in {"1", "2", "tests", "examples", "all", "full", ""}:
            if test_lines:
                panels.append(self.box_panel("TIER 2 — MOULINETTE TEST CASES & CAT -E ORACLE", test_lines, border_color="secondary"))

        if mode_key in {"3", "skeleton", "template", "all", "full"}:
            skel_colored = self.colorize_code("\n".join(skeleton_lines).rstrip(), show_lineno=True).splitlines()
            panels.append(self.box_panel("TIER 3 — CODE SKELETON & STRUCTURE", skel_colored, border_color="purple"))

        footer = [
            f"{self.bold('Hint Options')}: "
            f"{self.cmd('hint 1')} (Strategy & Traps) │ "
            f"{self.cmd('hint 2')} (Test Cases) │ "
            f"{self.cmd('hint 3')} (Code Skeleton)"
        ]
        panels.append("  " + footer[0])
        return "\n".join(panels)

    def scorecard_table(self, title: str, headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
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
        hdr_cells = [pad_visible(self.c(str(h).upper(), "muted"), col_widths[i]) for i, h in enumerate(headers)]
        sep_cells = [self.c("-" * col_widths[i], "muted") for i in range(col_count)]
        out.append("  " + "  ".join(hdr_cells).rstrip())
        out.append("  " + "  ".join(sep_cells).rstrip())
        for r in rows:
            cells = []
            for i in range(col_count):
                val = str(r[i]) if i < len(r) else ""
                cells.append(pad_visible(val, col_widths[i]) if i < col_count - 1 else val)
            out.append("  " + "  ".join(cells).rstrip())
        return "\n".join(out)

