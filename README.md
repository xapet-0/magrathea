# Magrathea

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Engine](https://img.shields.io/badge/Engine-Deepthought_5--Gate-0969da.svg)](#the-5-gate-evaluation-pipeline)
[![Curriculum](https://img.shields.io/badge/Curriculum-42_%2F_1337_Coding_School-2ea44f.svg)](#curriculum-coverage-439-exercises)
[![Exercises](https://img.shields.io/badge/Exercises-439_Materialized-brightgreen.svg)](#curriculum-coverage-439-exercises)
[![Memory_Runtime](https://img.shields.io/badge/Memory-Tsoding_Arena_%2B_Redzone_Canary-8a2be2.svg)](#memory-sentinel--arena-01-telemetry)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab.svg)](#system-requirements)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero_External-success.svg)](#key-capabilities)
[![Platform](https://img.shields.io/badge/Platform-Linux_%7C_macOS_%7C_WSL2-informational.svg)](#system-requirements)

**Magrathea** is an autonomous, zero-dependency offline simulation and continuous evaluation ecosystem for the **42 and 1337 Coding School** curriculum. It delivers an offline implementation of **ExamShell** (`v0.1.1`), the interactive curriculum browser and grader **Moulinette**, the headless 5-gate **Deepthought** evaluator, the **Pool Forge** (`pforge`) exercise packager, and the official **Norminette v3** and **Shnorm v4.2** linters.

Built for zero-setup portability and offline fidelity, Magrathea ships with **439 materialized exercises** (`136` C Piscine + `303` Exam), **20 official curriculum PDFs**, **17 Piscine modules**, **18 exam pools**, verified reference solutions in [`corrections/`](corrections/), a C11 linker-wrapped memory sentinel ([`sandbox_harness.c`](deepthought/sandbox_harness.c)) backed by [Tsoding Arena](third_party/tsoding_arena/arena.h), and a bundled pure-Python YAML parser ([`yaml/`](yaml/)) requiring zero external `pip` installs.

---

## Table of Contents

- [Key Capabilities](#key-capabilities)
- [Installation & Quick Start](#installation--quick-start)
- [CLI Tools & Command Reference](#cli-tools--command-reference)
  - [1. `moulinette` — Interactive Curriculum Explorer & Grader](#1-moulinette--interactive-curriculum-explorer--grader)
  - [2. `examshell` — Interactive Examination Terminal](#2-examshell--interactive-examination-terminal)
  - [3. `deepthought` — Headless 5-Gate Evaluator](#3-deepthought--headless-5-gate-evaluator)
  - [4. `norminette` & `shnorm` — 42 Coding Standard Linters](#4-norminette--shnorm--42-coding-standard-linters)
  - [5. `pforge` — Curriculum & Exercise Packager](#5-pforge--curriculum--exercise-packager)
  - [6. Cluster & Compatibility Utilities (`ft_lock`, `bc`, `ifconfig`)](#6-cluster--compatibility-utilities-ft_lock-bc-ifconfig)
- [Environment Variables](#environment-variables)
- [The 5-Gate Evaluation Pipeline](#the-5-gate-evaluation-pipeline)
- [Memory Sentinel & Arena-01 Telemetry](#memory-sentinel--arena-01-telemetry)
- [Curriculum Coverage (439 Exercises)](#curriculum-coverage-439-exercises)
- [Makefile Targets](#makefile-targets)
- [Repository Architecture](#repository-architecture)
- [System Requirements](#system-requirements)
- [Academic Integrity & Anti-Spoiler Policy](#academic-integrity--anti-spoiler-policy)
- [License](#license)

---

## Key Capabilities

* **Zero External Python Dependencies**: Uses only the Python 3.10+ standard library alongside a bundled pure-Python YAML 1.1 parser (`yaml/`), bundled official `norminette` (`3.3.60`), and bundled Tsoding `arena.h`. No virtual environment or internet access is required after checkout.
* **Hermetic 5-Gate Evaluation Pipeline**: Evaluates submissions sequentially through Turn-In/Norm/Makefile checks, `#include` & `nm -u` symbol whitelisting, `-Wall -Wextra -Werror` strict compilation, C11 memory-sentinel sandboxing, and differential/fixed-vector testing.
* **Complete 439-Exercise Catalog**: Every exercise includes `subject.en.txt`, `meta.yml`, `scale.yml`, boundary/edge-case `tests.yml`, and a reference implementation in `corrections/`.
* **Dual-Domain Memory Isolation (`Arena-01`)**: Internal harness metadata is allocated in a separate mmap region arena ([`trusted_harness/dt_arena.c`](trusted_harness/dt_arena.c)), isolated from student heap allocations (`malloc`/`calloc`/`realloc`/`strdup`/`free`) guarded by 16-byte front (`0x5A`) and rear (`0xA5`) redzone canaries.
* **Real & Practice (`--practice`) Exam Modes**: Supports realistic cluster conditions (local bare Vogsphere Git push verification, exponential cooldown timers, hidden `c_function` trace inputs) alongside a Practice mode for fast iterative debugging.
* **Cross-Platform Workspace Safety**: Runs on Linux (`x86_64` / `aarch64`), macOS, and Windows WSL2 with 79-column TUI compliance (`80x24` terminals), `NO_COLOR` support, and POSIX/NTFS-safe repository paths.

---

## Installation & Quick Start

Run directly from the repository root, or install system prerequisites and `~/.local/bin` symlinks with `./install.sh`:

```bash
# Audit OS toolchain, Python >= 3.10, official norminette, and ~/.local/bin links
./install.sh --check

# Install missing OS packages (apt/dnf/yum/pacman/zypper/xbps/apk/brew) and link tools
./install.sh --yes
```

`./install.sh` creates symlinks in `~/.local/bin` for `moulinette`, `deepthought`, `examshell`, `norminette`, `shnorm`, `ft_lock`, `bc`, `ifconfig`, `pforge`, and `audit_testers`.

Quick launch commands from the repository root:

```bash
make help               # Display quick-reference targets and commands
make check              # Verify OS tools, Python >= 3.10, and bundled norminette
make list               # List all 17 C Piscine modules and 18 Exam pools
./bin/moulinette        # Launch interactive Moulinette curriculum explorer & grader
./bin/examshell         # Launch interactive ExamShell (Real Mode)
./bin/examshell --practice   # Launch ExamShell in Practice / Coaching Mode
```

---

## CLI Tools & Command Reference

### 1. `moulinette` — Interactive Curriculum Explorer & Grader

Dual-mode TUI/REPL and direct CLI for browsing the 439-exercise catalog, inspecting subjects, watching files on save, and grading Piscine modules or Exam exercises.

```bash
./bin/moulinette [target] [extra ...] [options]
```

**CLI Subcommands & Shortcuts:**

```bash
./bin/moulinette                        # Launch bounded viewport TUI / REPL
./bin/moulinette guide [exercise]       # Step-by-step first-time walkthrough
./bin/moulinette doctor                 # Audit compilers, POSIX tools, TMPDIR & PATH
./bin/moulinette --list [module|track]  # List modules, exam tracks, or exercises
./bin/moulinette --catalog              # Display complete Piscine & Exam catalog
./bin/moulinette subject ft_putchar     # Format and print subject specification
./bin/moulinette init ft_putchar        # Optionally create turn-in folder & starter stub
./bin/moulinette ft_putchar             # Grade one exercise directly
./bin/moulinette c04/ft_putnbr          # Disambiguate an exercise name shared across modules
./bin/moulinette c00                    # Grade an entire Piscine module (ex00 upwards)
./bin/moulinette --watch ft_strjoin     # Re-grade automatically whenever files change
./bin/moulinette --json ft_putchar      # Grade once and emit structured JSON (no XP credit)
```

**CLI Options (`./bin/moulinette --help`):**

| Option | Argument | Description |
| :--- | :--- | :--- |
| `--subject` | `SUBJECT` | Subject identifier (e.g., `ft_strlen` or `c01/ft_strlen`). |
| `--module` | `MODULE` | Grade an entire Piscine module (e.g., `c00`..`c13`, `shell00`, `shell01`, `rush_bsq`). |
| `--dir`, `--path` | `DIR` | Override turn-in directory containing submission files. |
| `--exam` | — | Prefer exam namespace and disable Norminette unless `--norm` is passed. |
| `--norm` | — | Force official 42 Norminette check even in exam mode. |
| `--strict` | — | Strict Piscine mode (Norminette + forbidden symbol enforcement). |
| `--init` | — | Scaffold turn-in folder with 42 header and `subject.en.txt`. |
| `--show-subject`, `-S` | — | Print formatted `subject.en.txt` for the exercise and exit. |
| `--practice`, `--mode` | `{real,practice}` | Enable Practice mode or select operating mode (default: `real`). |
| `--watch` | — | Watch source files and re-grade automatically on modification. |
| `--list` | `[LIST]` | List Piscine modules, Exam tracks, or exercises inside a filter. |
| `--catalog` | — | Display full Piscine & Exam catalog and exit. |
| `--trace-out` | `TRACE_OUT` | Save Deepthought trace to a custom file path. |
| `--xp-ledger` | `XP_LEDGER` | Use an alternate XP ledger JSON file (never credits main profile). |
| `--theme` | `PALETTE` | Terminal palette: `42-cluster` (default), `gruvbox`, `jcluzet-exam`, `tokyo-night`. |
| `--self-test` | — | Developer verification: grade reference implementation in `corrections/`. |
| `--json` | — | Grade one single exercise and output JSON (cannot combine with `--watch` or `--module`; no XP recorded). |
| `--alt-screen` | — | Force bounded alternate-screen viewport (default on interactive TTY). |
| `--scrollback` | — | Force classic scrollback REPL instead of alternate-screen viewport. |
| `--trace-mode` | `{real,helpful}` | Trace detail: `real` (42 hidden `c_function` inputs/diffs, default) or `helpful` (unified diffs). |
| `--helpful` | — | Shortcut for `--trace-mode helpful`. |
| `--no-color` | — | Disable ANSI colors. |

**Interactive TUI / REPL Commands:**

| Category | Command(s) | Action |
| :--- | :--- | :--- |
| **Help & Check** | `help`, `?` | Show command summary inside interactive session. |
| | `guide [ex]`, `start`, `howto` | Print step-by-step first-time guide (`ex` optional). |
| | `doctor`, `check`, `setup`, `diagnose` | Inspect system toolchain, compilers, norminette, and exec temp space. |
| | `xp`, `stats`, `history` | Display student XP progression, level, and completed exercises. |
| **Navigation** | `1`, `piscine`, `use piscine`, `cd piscine` | Enter C Piscine & Shell module browser. |
| | `2`, `exams`, `exam`, `piscine exam` | Enter Cluster Exam tracks browser. |
| | `<module>` / `0`..`13` | Open module (`c00`..`c13`, `shell00`, `shell01`, `rush_bsq`; `0`..`13` inside `piscine`). |
| | `<track>` / `1`..`N` | Open an exam track; inside a track, `level<N>` / `lvl<N>` / `<N>` opens that level. |
| | `back`, `b`, `..`, `prev`, `up`, `cd ..` | Return to previous catalog view / navigation level. |
| | `forward`, `f`, `next`, `redo` | Move forward in navigation history. |
| | `home`, `root`, `top` | Jump back to main catalog home screen. |
| | `list [target]`, `ls`, `catalog` | Refresh current view or list filtered module/track exercises. |
| | `clear`, `cls` | Clear content area and redraw current screen. |
| | `q`, `quit`, `exit` | Exit interactive session. |
| **Work & Grading** | `subject <ex>`, `-s <ex>` | Display `subject.en.txt` and expected turn-in directory. |
| | `init <ex>` | Optionally create the turn-in folder and empty starter stub. |
| | `<ex>` / `grade <ex|module>` / `eval ...` | Grade an exercise or current module; supports inline `--strict`, `--norm`, `--exam`, `--watch`, `--self-test`, `--trace-mode real\|helpful`, `--helpful`, `--dir <path>`. |
| | `watch <ex>`, `-w <ex>` | Continuously re-grade `<ex>` on file save (`Ctrl+C` stops watch loop). |
| **Traces & Pager** | `trace` | View the most recent Deepthought trace. |
| | `trace-mode [real\|helpful]` | View or switch trace verbosity for subsequent grades. |
| | `more` | Open scrollable viewport pager on last displayed output. |
| | `less [trace \| subject <ex>]` | Page through output, last trace, or a formatted subject. |
| **Pager Keys** | `j` / `Enter` | Scroll down half page. |
| | `k` / `b` / `p` | Scroll up half page. |
| | `g` / `G` | Jump to top (`g`) or bottom (`G`) of output. |
| | `q` | Return from pager to prompt. |

**Turn-In Rules ("The 42 way"):**
* In the module header (`subject : subjects/piscine/c00/<name>/subject.en.txt` and `turn-in : workspace/piscine/c00/<ex>/`), `<ex>` refers to the **EX** column (`ex00`..`ex08`) and `<name>` refers to the **ASSIGNMENT** column (e.g., `ft_putchar`), relative to the repository root:
  * **Subject path (e.g. `ex00` / `ft_putchar`):** [`subjects/piscine/c00/ft_putchar/subject.en.txt`](subjects/piscine/c00/ft_putchar/subject.en.txt) (`~/Desktop/magrathea/subjects/piscine/c00/ft_putchar/subject.en.txt`)
  * **Turn-in folder path (e.g. `ex00`):** `~/Desktop/magrathea/workspace/piscine/c00/ex00/`
* **Fastest ways to open subjects or create turn-in folders without typing full paths:**
  1. Inside `moulinette (piscine/c00)>`:
     ```text
     subject ex00      # Display the subject
     init ex00         # Create turn-in folder + starter stub (or: init c00 for all ex00..ex08)
     ```
  2. Directly from your terminal (from any directory):
     ```bash
     moulinette subject c00/ex00
     moulinette init c00/ex00
     cd ~/Desktop/magrathea/workspace/piscine/c00/ex00
     ```
  3. Or manually create `<module>/<exNN>/` and write your solution file inside it:
     ```bash
     mkdir -p workspace/piscine/c00/ex00
     $EDITOR workspace/piscine/c00/ex00/ft_putchar.c
     ./bin/moulinette ft_putchar
     ./bin/moulinette c00
     ```
* Grader resolution checks `--dir <path>`, then an active `<exNN>/` / `<module>/` directory you are standing inside (useful for cloned Piscine repos), then `workspace/piscine/<module>/<exNN>/` (or `workspace/exams/<ex>/` for exams).
* Shared names go to Piscine first (`--exam` flips priority); equal-claim names like `ft_putnbr` (`c00` and `c04`) require explicit qualification (`c00/ft_putnbr` or `c04/ft_putnbr`).
* Validated XP is credited once per exercise in `workspace/xp_ledger.json`; `--xp-ledger`, `--self-test`, and `--json` do not modify your profile ledger. Traces are saved in `workspace/traces/`.

---

### 2. `examshell` — Interactive Examination Terminal

Simulates the 42 / 1337 ExamShell (`v0.1.1`) in an `80x24`-compliant terminal viewport with countdown timers, random exercise draws per level, bare Vogsphere Git push verification (`~/exam-basedir`), and cooldown management.

```bash
./bin/examshell [pool] [options]
```

**Pool Shorthands:**
`exam00` (`00`), `exam01` (`01`), `exam02` (`02`), `examfinal` (`final`), `1337-c-exam-00`..`1337-c-exam-final`, `full` (`classic_42_full`), and `rank02`..`rank06` (`rank2`..`rank6`). Omit `[pool]` on an interactive TTY to launch the graphical session-selection menu.

**CLI Options (`./bin/examshell --help`):**

| Option | Argument | Description |
| :--- | :--- | :--- |
| `pool`, `-p`, `--pool` | `POOL` | Exam pool ID or shorthand alias (e.g., `c_piscine_exam_00`, `exam00`, `rank03`). |
| `-m`, `--menu` | — | Display official exam tracks menu and exit. |
| `--mode` | `{real,test,practice}` | Session mode (default: `real`). |
| `--practice` | — | Alias for `--mode practice` (unlocks coaching tools). |
| `--duration` | `SECONDS` | Override session timer duration in seconds (`> 0`). |
| `-l`, `--level` | `LEVEL` | Starting exam level index. |
| `-s`, `--seed` | `SEED` | Deterministic random seed for candidate pool draw. |
| `--login` | `LOGIN` | Override student login (defaults to `$USER` / `$LOGNAME`). |
| `-b`, `--basedir`, `--workspace` | `BASEDIR` | Custom exam working directory (default: `~/exam-basedir`). Safety-validated against system/`$HOME` data directories. |
| `--fresh` | — | Start a fresh session instead of resuming. |
| `-r`, `--resume` | — | Resume existing `.session.json` state inside `basedir`. |
| `-t`, `--theme` | `PALETTE` | Palette: `42-cluster`, `gruvbox`, `jcluzet-exam`, `tokyo-night`. |
| `-c`, `--command` | `COMMAND` | Execute semicolon/newline-separated command(s) non-interactively and exit. |
| `--trace-mode` | `{real,helpful}` | Default trace detail (`real` hides `c_function` expressions/diffs). |
| `--helpful` | — | Shortcut for `--trace-mode helpful`. |
| `--cooldown-mode` | `{real,linear}` | Cooldown scaling after failed `grademe`: `real` (`1m -> 2m -> 4m...`, default) or `linear` (`+30s`). |
| `--no-color` | — | Disable ANSI colors. |

**Interactive ExamShell Commands (`examshell>`):**

| Availability | Command(s) | Description |
| :--- | :--- | :--- |
| **Core (All Modes)** | `status` | Display current level, grade, attempt history, Vogsphere repo, and remaining timer. |
| | `grademe` | Verify Vogsphere Git push and submit `rendu/<assignment>` to Deepthought (`--now` available in practice mode). |
| | `finish`, `exit`, `quit` | Conclude the exam session and print summary score. |
| **Helper (All Modes)** | `subject [options]`, `sub` | Render current `subject.en.txt` (`subject --full` or `subject --raw`). |
| | `trace`, `trace mode [real\|helpful]` | Show last Deepthought trace or change trace verbosity. |
| | `logs [--pager]`, `diagnostics` | Show Vogsphere repository initialization and infrastructure logs. |
| | `more`, `pager` | Scroll last command output inside viewport pager (`j`/`k`/`Space`/`g`/`G`/`q`). |
| | `clean` | Remove compiled artifacts (`a.out`, `*.o`, swap files) from `rendu/` safely. |
| | `clear`, `cls` | Redraw viewport cleanly without clearing session state. |
| | `time` | Print local clock, session start/end timestamps, elapsed time, and remaining countdown. |
| | `history` | Show command and grading attempt history for the active session. |
| | `guidelines`, `rules` | Display 42 / 1337 Exam General & Coding Guidelines. |
| | `help [cmd]`, `tools`, `tool`, `?` | Display available commands and per-command usage help. |
| | `klist`, `kinit [login]`, `ssh_key [path\|key]` | Inspect simulated Kerberos ticket cache or register an SSH public key for Vogsphere diagnostics. |
| **Practice Only (`--practice`)** | `init`, `scaffold` | Create `rendu/<assignment>/` with 42 header & starter prototype. |
| | `edit`, `vim`, `nano`, `code` | Scaffold if needed and open current assignment in `$EDITOR` / `vim` / `nano` / `code`. |
| | `run [args...]` | Compile submission in `rendu/<assignment>` and execute directly with arguments. |
| | `check`, `test` | Run local 5-gate pre-flight evaluation on `rendu/<assignment>` without consuming cooldown or requiring push. |
| | `push` | Stage, commit, and push `rendu/` changes to the local bare Vogsphere repository. |
| | `assign <slug>` | Switch active exercise slug within Practice mode. |
| | `list`, `level <N>`, `reroll`, `next` | List pool levels, jump to level `N`, or draw a different exercise at current level. |
| | `diff` | Print unified output diff from the most recent failed trace. |
| | `norm [on\|off]`, `enable <f>`, `disable <f>` | Toggle Norminette enforcement during Practice exams. |
| | `cooldown [...]`, `remove_grade_time` | Inspect/reset/configure `grademe` wait timer (`mode real\|linear\|reset\|off\|on\|<sec>`). |
| | `force_success` | Force-validate current assignment in Practice mode and advance to the next level. |
| | `theme <palette>` | Switch UI palette live (`42-cluster`, `jcluzet-exam`, `tokyo-night`, `gruvbox`, `plain`). |
| | `menu`, `sessions` | View official exam track table / session selection reference. |

> **TTY Controls:** On an interactive terminal, `Ctrl+C` clears the current prompt line without killing your active exam session, `Ctrl+L` clears and redraws the viewport, and `Ctrl+D` (`EOF`) exits cleanly. Solution disclosure commands (`solution`, `solve`, `hint`) remain permanently disabled in both Real and Practice modes.

---

### 3. `deepthought` — Headless 5-Gate Evaluator

Direct non-interactive runner for grading individual exercises or full Piscine modules in shell pipelines and CI checks.

```bash
./bin/deepthought <module>                         # Evaluate entire Piscine module (e.g., c00, shell00)
./bin/deepthought grade <exercise> [--dir DIR]     # Evaluate a single exercise through all 5 gates
./bin/deepthought status                           # Print XP progression and engine status
./bin/deepthought help                             # Show usage summary
```

**Options (`./bin/deepthought --help`):**

| Option | Argument | Description |
| :--- | :--- | :--- |
| `--module` | `MODULE` | Explicit Piscine module slug. |
| `--dir`, `--path` | `DIR` | Override student submission directory. |
| `--strict` | — | Enable strict sandbox & dual-compiler checks (`gcc` / `clang`). |
| `--self-test` | — | Grade reference implementations in `corrections/`. |
| `--trace-out` | `TRACE_OUT` | Save generated Deepthought trace to a custom file path. |
| `--trace-mode` | `{real,helpful}` | Trace detail mode (`real` hides `c_function` expressions/diffs). |
| `--helpful` | — | Shortcut for `--trace-mode helpful`. |
| `--theme` | `PALETTE` | Output color theme (`42-cluster`, `gruvbox`, `jcluzet-exam`, `tokyo-night`). |
| `--no-color` | — | Disable ANSI colors. |

---

### 4. `norminette` & `shnorm` — 42 Coding Standard Linters

#### `bin/norminette` (Official 42 Norminette `3.3.60`)
Runs the unmodified official [42school/norminette](https://github.com/42school/norminette) package shipped inside [`third_party/norminette/`](third_party/norminette/) via `python3 -I` so local files or `PYTHONPATH` cannot shadow it.

```bash
./bin/norminette workspace/                        # Check workspace recursively
./bin/norminette -R CheckDefine ft_abs.h           # Enable macro definition rule (C 08)
./bin/norminette -f json workspace/c00             # Emit JSON diagnostics
./bin/norminette -v                                # Print bundled version
python3 third_party/update_norminette.py 3.3.60    # Update wheel from PyPI (sha256 verified)
```

Options: `[file ...]`, `-d/--debug`, `-o/--only-filename`, `-v/--version`, `--cfile`, `--hfile`, `--filename`, `--use-gitignore`, `-f {json,humanized}`, `--no-colors`, `-R <rule>`. If no Python `>= 3.10` interpreter is available, `bin/norminette` fails closed with exit code `127` (no imitation fallback); run `./install.sh` to provision Python 3.10+.

#### `bin/shnorm` (42 / 1337 Sh-Norm v4.2)
POSIX shell static analyzer enforcing 37 style and safety rules across `.sh` scripts.

```bash
./bin/shnorm install.sh bocal/*.sh                 # Lint shell scripts strictly
./bin/shnorm -1 workspace/piscine/shell00/ex00     # One-liner Piscine mode (relaxes set -eu)
./bin/shnorm --list-rules                          # List all 37 Sh-Norm v4.2 rules
./bin/shnorm --explain SH-N001                     # Explain a rule in English & Darija
./bin/shnorm --generate-header my_script.sh        # Print a 42-compliant shell header
```

Options: `[targets ...]`, `-1/--oneliner`, `--no-color`, `-e/--explain RULE_CODE`, `-l/--list-rules`, `--generate-header FILENAME`.

---

### 5. `pforge` — Curriculum & Exercise Packager

Tooling for scaffolding 4-component exercises (`subject.en.txt`, `meta.yml`, `scale.yml`, `tests.yml`), rebuilding catalog state, and exporting student packs without test suites or reference solutions.

```bash
./bin/pforge --status
./bin/pforge --scaffold my_ex --type c_program --category exams --allowed "write,malloc,free"
./bin/pforge --export-student-pack /tmp/magrathea-student
./bin/pforge --export-dev-pack /tmp/magrathea-review --archive-base /tmp/magrathea-review
```

| Option | Argument | Description |
| :--- | :--- | :--- |
| `--scaffold` | `SLUG` | Create a new 4-component exercise skeleton under `subjects/<category>/<slug>/`. |
| `--type` | `{c_function,c_program,c_header,makefile,shell,python,cpp}` | Exercise evaluation mode (default: `c_program`). |
| `--category` | `CATEGORY` | Target category path under `subjects/` (default: `exams`). |
| `--allowed` | `ALLOWED` | Comma-separated allowed functions or shell commands (default: `write`). |
| `--files` | `FILES` | Space-separated expected turn-in files. |
| `--materialize-all` | — | Rematerialize exercises, corrections, and pools from catalog definitions. |
| `--export-student-pack` | `DIR` | Export clean student distribution stripping `tests.yml`, `corrections/`, and internal test suites. |
| `--export-dev-pack` | `DIR` | Export review bundle containing exercises, examples, tests, and reference corrections. |
| `--archive-base` | `BASE_PATH` | Also write `.tar.gz` and `.zip` archives at `BASE_PATH` during `--export-dev-pack`. |
| `--status` | — | Display current engine inventory counts and structure status. |

---

### 6. Cluster & Compatibility Utilities (`ft_lock`, `bc`, `ifconfig`)

* **`bin/ft_lock`** — Cluster workstation screen locker & idle reporter (`--status`, `--check-idle`, `--dry-run`, `--config CONFIG`). Verifies D-Bus session ownership before invoking desktop lockers and confirms lock activation via D-Bus or `systemd-logind`.
* **`bin/bc`** — POSIX.1-2024 arbitrary-precision calculator (`usage: bc [-hlqsvVw] [file ...]`). Delegates transparently to the host's system `bc` when installed (normalizing `-V` to `-v`), and provides a pure-Python arbitrary-precision fallback (`ibase`/`obase`, `scale`, `-l` mathlib) when `FT_BC_INTERNAL=1` or no system `bc` exists.
* **`bin/ifconfig`** — Network interface shim (`[-l | -d | iface] [link | ether]`) for `shell01/mac.sh` and sandboxed runs. Delegates transparently to host `ifconfig` when present unless sandboxed via `DT_SANDBOX_IFCONFIG=1` or mock environment variables (`DT_LIVE_IFCONFIG=1`, `DT_MOCK_ETHER`, `DT_IFCONFIG_STYLE=bsd|openbsd`).

---

## Environment Variables

| Variable | Tool(s) | Purpose |
| :--- | :--- | :--- |
| `NO_COLOR`, `FORCE_COLOR` | All CLIs | Disable ANSI color escapes (`NO_COLOR=1`) or force colors in non-TTY pipes (`FORCE_COLOR=1`). |
| `PAGER` | `moulinette`, `examshell` | Override trace/subject pager command (defaults to `less -FR` in `moulinette`). |
| `EDITOR` | `examshell` | Preferred editor launched by `edit` in `--practice` mode. |
| `MOULINETTE_SCROLLBACK`, `MOULINETTE_ALT_SCREEN` | `moulinette` | Set `MOULINETTE_SCROLLBACK=1` (or `MOULINETTE_ALT_SCREEN=0` / `MOULINETTE_NO_CLEAR=1`) to force classic scrollback mode. |
| `MOULINETTE_DEBUG` | `moulinette` | Print full tracebacks inside REPL commands instead of keeping errors localized. |
| `FT_STUDENT_PROFILE` | `deepthought` | Override student profile YAML file path. |
| `MAGRATHEA_EXEC_TMPDIR` | `deepthought` | Override executable scratch build directory used for C/C++ sandbox binaries. |
| `DT_REQUIRE_NAMESPACE_SANDBOX` | `deepthought` | Require Linux `CLONE_NEWUSER \| CLONE_NEWNS` namespace masking (`1`) instead of best-effort fallback. |
| `FT_BC_INTERNAL`, `BC_LINE_LENGTH` | `bc` | Force built-in Python `bc` engine (`1`) and configure output wrap width (default `70`). |
| `DT_SANDBOX_IFCONFIG`, `DT_LIVE_IFCONFIG`, `DT_MOCK_ETHER` | `ifconfig` | Force deterministic cluster mock interfaces, host sysfs MAC lookup, or custom MAC output. |
| `DT_SKIP_HOME_SYMLINKS` | `examshell`, `vogsphere` | Skip automatic `~/rendu` symlink creation in isolated runs (`1`). |

---

## The 5-Gate Evaluation Pipeline

Every student submission is evaluated sequentially through five stages in [`deepthought/grader.py`](deepthought/grader.py). Failure at any stage stops execution and produces the corresponding diagnostic verdict:

| Gate | Stage | Mechanism | Diagnostic Verdicts |
| :---: | :--- | :--- | :--- |
| **1** | **Turn-In, Norm & Repository Gate** | Validates expected filenames, rejects symlinks and extraneous files, verifies `Makefile` rules (`all`, `clean`, `fclean`, `re`, relink check) via [`makefile_and_repo.py`](deepthought/makefile_and_repo.py), and runs `norminette` / `shnorm`. | `Nothing turned in` / `Norme KO` / `Makefile KO` |
| **2** | **AST & Symbol Whitelist Gate** | Pre-scans C/C++ sources for forbidden `#include` directives, `switch` restrictions where applicable, or unauthorized `main()` definitions, then inspects compiled object symbols via `nm -u` against `allowed_functions` in `meta.yml`. | `Cheating (-42)` / `Forbidden function` |
| **3** | **Strict Compilation Gate** | Compiles student sources alongside the generated test harness under `-Wall -Wextra -Werror` inside an isolated temporary build directory. | `Does not compile` |
| **4** | **Sandbox & Memory Sentinel Gate** | Executes compiled binaries with resource limits (`RLIMIT_AS`/`RLIMIT_CPU`/`RLIMIT_NPROC`), kernel-permitted masking of `corrections/`, `subjects/`, and `pools/` (`unshare`), and Linux linker-wrapped heap/redzone instrumentation (Gates 1–3 & 5 active on macOS). | `Timeout` / `Segfault` / `Bus error` / `Abort` / `Leak KO` / `Redzone KO` / `Invalid Free KO` / `Double/Invalid Free KO` |
| **5** | **Differential & Edge-Case Oracle** | Runs fixed, boundary, and oracle test vectors from `tests.yml`, comparing `stdout`, `stderr`, exit status, and mutated state against reference expectations. | `KO :(` / `OK :)` (`100/100`) |

---

## Memory Sentinel & Arena-01 Telemetry

Magrathea's C11 runtime harness ([`deepthought/sandbox_harness.c`](deepthought/sandbox_harness.c) and [`trusted_harness/`](trusted_harness/)) enforces strict isolation between harness allocations (guarded `mmap` Arena-01 regions with trailing `PROT_NONE` pages) and student heap memory on Linux/WSL2 (`GNU ld`) via linker wrapping (`-Wl,--wrap=malloc,calloc,realloc,reallocarray,strdup,strndup,free,read,exit,_exit,_Exit`):

| Exit / Signal Code | Diagnostic Status | Condition Trapped by `sandbox_harness.c` |
| :---: | :--- | :--- |
| **`0`** | `OK :)` | All test vectors passed with zero leaked blocks and intact redzones. |
| **`42`** | `Leak KO` | Student code left unfreed heap blocks at exit (`DT_CHECK_LEAKS=1`). |
| **`43`** | `Redzone KO` | Student code corrupted 16-byte front (`0x5A`) or rear (`0xA5`) heap redzone canaries. |
| **`44`** | `Invalid Free KO` | Student attempted `free()`/`realloc()` on a harness arena pointer or an untracked/misaligned pointer. |
| **`45`** | `Allocation Tracking Exhausted KO` | Allocation tracking capacity exceeded inside harness telemetry (`g_max_allocs` / OOM). |
| **`46`** (or `6` + marker) | `Double/Invalid Free KO` | Double free trapped during heap node validation or allocator abort. |
| **`-6` / `-7` / `-8` / `-11`** | `Abort` / `Bus error` / `FPE` / `Segfault` | Process killed by `SIGABRT` (`-6`), `SIGBUS` (`-7`), `SIGFPE` (`-8`), or `SIGSEGV` (`-11`) — distinct from normal positive exits. |

---

## Curriculum Coverage (439 Exercises)

All **439 exercises** are materialized under [`subjects/`](subjects/) with matching reference solutions under [`corrections/`](corrections/):

### 1. C & Shell Piscine — 17 Modules (`136` Exercises)

| Module | Topic | Exercises | Official PDF |
| :--- | :--- | :---: | :--- |
| `shell00` | UNIX Shell & Git Essentials | `10` | `subjects/piscine/shell00/Shell_00.pdf` |
| `shell01` | Shell Scripting & Pipelines | `8` | `subjects/piscine/shell01/Shell_01.pdf` |
| `c00` | First Steps in C (`write`, loops, combinations) | `9` | `subjects/piscine/c00/C_00.pdf` |
| `c01` | Pointers, Dereferencing & Array Sorting | `9` | `subjects/piscine/c01/C_01.pdf` |
| `c02` | Strings, Buffers & Memory Hex Dump (`ft_print_memory`) | `13` | `subjects/piscine/c02/C_02.pdf` |
| `c03` | String Comparison, Concatenation & Search | `6` | `subjects/piscine/c03/C_03.pdf` |
| `c04` | Number Formatting & Base Conversion (`ft_atoi_base`, `ft_putnbr_base`) | `6` | `subjects/piscine/c04/C_04.pdf` |
| `c05` | Recursion, Factorials, Primes & `N`-Queens (`ft_ten_queens_puzzle`) | `9` | `subjects/piscine/c05/C_05.pdf` |
| `c06` | Command-Line Arguments (`argc` / `argv`) | `4` | `subjects/piscine/c06/C_06.pdf` |
| `c07` | Dynamic Memory Allocation (`malloc`, `ft_split`, `ft_convert_base`) | `7` | `subjects/piscine/c07/C_07.pdf` |
| `c08` | Preprocessor Macros, Structs & Header Files (`.h`) | `6` | `subjects/piscine/c08/C_08.pdf` |
| `c09` | Static Libraries (`libft.a`) & `Makefile` Automation | `3` | `subjects/piscine/c09/C_09.pdf` |
| `c10` | File Descriptors & UNIX Utilities (`ft_display_file`, `ft_cat`, `ft_tail`, `ft_hexdump`) | `4` | `subjects/piscine/c10/C_10.pdf` |
| `c11` | Function Pointers & Higher-Order Array Operations | `8` | `subjects/piscine/c11/C_11.pdf` |
| `c12` | Singly Linked Lists (`t_list` creation, sorting, removal, merging) | `18` | `subjects/piscine/c12/C_12.pdf` |
| `c13` | Binary Search Trees (`t_btree` traversals, level-order, apply) | `8` | `subjects/piscine/c13/C_13.pdf` |
| `rush_bsq` | Rushes & Bonus (`rush00`–`rush02`, `colle02`, `match_n_match`, `sastantua`, `sudoku`, `bsq`) | `8` | `subjects/piscine/rush_bsq/*.en.pdf` |

### 2. Cluster Examinations — 18 Pool Definitions (`303` Unique Exercises)

* **42 / 1337 Piscine Exams**: `c_piscine_exam_00`, `c_piscine_exam_01`, `c_piscine_exam_02`, `c_piscine_final_exam`, `1337_classic_exam00`, `1337_classic_exam01`, `1337_classic_exam02`, `1337_classic_examfinal`.
* **Common Core & Extended Tracks**: `rank02`, `rank03`, `rank04`, `rank05`, `rank06`, `new_2026_exam`, `classic_42_full`, `cursus_rank03_06`, `piscine_reloaded`, `day09`.

---

## Makefile Targets

```bash
make help       # Display quick-reference banner and common targets
make check      # Check host compilers, Python >= 3.10, and official norminette
make install    # Install missing system prerequisites and sync ~/.local/bin links
make list       # Display all 17 C Piscine modules and 18 Exam pools
make piscine    # Launch interactive Moulinette curriculum explorer
make exam       # Launch interactive ExamShell (Real Mode)
make practice   # Launch interactive ExamShell in Practice Mode
make norm       # Run official 42 norminette on workspace/
make shnorm     # Run Sh-Norm v4.2 on install.sh, shell shims, and bocal/*.sh
make test       # Run the Python unittest suite (tests/test_*.py)
make clean      # Remove workspace traces, runtime artifacts, and Python bytecode caches
```

---

## Repository Architecture

```text
magrathea/
├── LICENSE                       # MIT License
├── Makefile                      # Quick-launch and verification targets
├── pyproject.toml                # Package metadata, pytest & ruff settings
├── install.sh                    # Cross-OS prerequisite installer & symlink manager
├── README.md                     # User & CLI documentation
├── bin/                          # CLI executables and wrapper scripts
│   ├── moulinette                # Interactive curriculum browser, scaffolder & grader
│   ├── examshell                 # Interactive 42 / 1337 examination terminal (v0.1.1)
│   ├── deepthought               # Headless 5-gate evaluator CLI
│   ├── norminette                # Wrapper running bundled official 42 norminette
│   ├── shnorm                    # POSIX Shell Norm v4.2 static linter
│   ├── pforge                    # Curriculum exercise & package builder
│   ├── ft_lock                   # Cluster session screen locker & idle checker
│   ├── bc                        # System-delegating / standalone POSIX bc engine
│   ├── ifconfig                  # System-delegating / sandbox mock ifconfig
│   ├── audit_testers             # 6-mode subject integrity auditor
│   ├── auto_correc_main.sh       # Differential C grader helper script
│   └── compare_subjects.sh       # Subject specification comparator launcher
├── bocal/                        # Workstation provisioning & shell setup helpers
├── corrections/                  # Verified reference implementations (439 exercises)
│   ├── exams/                    # 303 Exam reference implementations
│   └── piscine/                  # 136 Piscine reference implementations
├── deepthought/                  # Core Python grading engine & C11 sandbox source
│   ├── grader.py                 # 5-gate evaluation pipeline & harness codegen
│   ├── scorecard.py              # Shared 5-gate summary & tilde-path formatter
│   ├── compiler_and_symbols.py   # Header include guard & nm -u symbol analyzer
│   ├── makefile_and_repo.py      # Makefile rule & relink verifier
│   ├── shell_evaluator.py        # Shell exercise evaluator & fixture runner
│   ├── sandbox_harness.c         # Linker-wrapped heap canary, leak & exit sentinel
│   ├── vogsphere.py              # Local bare Git repo & exponential cooldown logic
│   ├── progression.py            # XP ledger, rank progression & profile storage
│   ├── pool_forge.py             # Exercise scaffolder & distribution exporter
│   ├── catalog.py                # Exam duration & catalog helper utilities
│   ├── cli_wrapper.py            # Shared CLI invocation & argument helpers
│   ├── subject_examples.py       # Subject example extractor & normalizer
│   ├── subject_comparer.py       # Subject text comparator utility
│   ├── test_telemetry.py         # Harness telemetry contract & freshness helpers
│   └── ui_theme.py               # ANSI/VT100 palette, viewport & pager engine
├── docs/                         # Technical specifications & 42 coding guidelines
├── pools/                        # 17 Piscine catalogs, 18 Exam manifests & aliases
├── subjects/                     # 439 exercise folders + 20 official curriculum PDFs
├── templates/                    # YAML and subject templates
├── tests/                        # Automated Python test suites (unittest)
├── third_party/                  # Bundled upstream dependencies (MIT)
│   ├── norminette/               # Unmodified official 42 norminette (3.3.60)
│   ├── tsoding_arena/            # Region arena allocator (arena.h)
│   └── update_norminette.py      # PyPI sha256-verified norminette updater
├── trusted_harness/              # C11 harness arena, compiler guard & diagnostics
├── vogsphere/                    # Runtime bare Git repository storage (.gitkeep)
├── workspace/                    # Student turn-in workspace, traces & XP ledger
└── yaml/                         # Bundled pure-Python PyYAML 6.0.1 runtime
```

---

## System Requirements

* **Operating System**:
  * **Linux (`x86_64` / `aarch64`) & Windows WSL2**: Full **5-Gate Pipeline** including GNU `ld` static linker wrapping (`-Wl,--wrap=...`) C11 Memory Sentinel (`DT_CHECK_LEAKS`, redzones, double-free detection) and unprivileged `CLONE_NEWUSER | CLONE_NEWNS` namespace masking when permitted by the host kernel.
  * **macOS (`darwin`, Apple `ld64`)**: Supports **Gates 1–3 & Gate 5** (Norminette, `nm -u` symbol whitelist, `-Wall -Wextra -Werror` compilation, `rlimit`/session-group isolation, and differential oracle). Gate 4 `-Wl,--wrap` linker interception is Linux/WSL2 `GNU ld` specific and omitted automatically on macOS.
* **Python Runtime**: Python `3.10+` (standard library only; required by both type annotations and bundled official `norminette` `3.3.60`). Run `./install.sh` if your OS ships an older Python.
* **Compilers**: `gcc` or `clang` (with `g++` / `clang++` for Rank 05 C++ exercises).
* **UNIX Toolchain**: `git`, `make`, `nm`, `ar`, `sh`, `diff`, `tar`.

---

## Academic Integrity & Anti-Spoiler Policy

Reference implementations in [`corrections/`](corrections/) exist on disk in this offline kit strictly as local golden oracles for Gate 5 twin-execution evaluation (never encrypted). Magrathea enforces anti-spoiler boundaries across workflows:
1. **CLI & REPL Spoiler Lock**: Solution/hint disclosure commands (`solve`, `solution`, `--solve`, `--solution`, `hint`, `--hint`) and explicit path references to `corrections/` inside `examshell` or `--dir corrections/...` (without `--self-test`) are blocked with exit status `2`.
2. **Sandbox Namespace Masking**: During binary execution on Linux kernels that permit unprivileged user namespaces, `corrections/`, `subjects/`, and `pools/` are masked with an unreadable `mode=000` `tmpfs` inside `CLONE_NEWUSER | CLONE_NEWNS` (`unshare`), while C/C++ sources are pre-scanned (including line-splice normalization) to reject unauthorized `#include` paths. Hosts restricting unprivileged userns fall back to `rlimit` and session-group isolation (visible in `./moulinette doctor`).
3. **Diagnostic-Driven Debugging**: Failed evaluations (`KO`) are diagnosed via compiler errors, Arena-01 memory sentinel status codes, and trace diffs (`--trace-mode helpful`).

---

## License & Third-Party Notices

* **Magrathea Engine & Tooling**: Licensed under the **MIT License** — see [`LICENSE`](LICENSE) for full details.
* **Bundled Open-Source Dependencies** (MIT License):
  * **Official 42 Norminette (`3.3.60`)**: [`third_party/norminette/`](third_party/norminette/) — Copyright (c) 2020 42 Association ([`SOURCE.txt`](third_party/norminette/SOURCE.txt)).
  * **Tsoding Arena (`arena.h`)**: [`third_party/tsoding_arena/arena.h`](third_party/tsoding_arena/arena.h) — Copyright (c) 2022 Alexey Kutepov.
  * **PyYAML (`6.0.1`)**: [`yaml/`](yaml/) — MIT-licensed pure-Python YAML parser.
* **Curriculum Content (`subjects/`)**: Official 42 / 1337 assignment PDFs (`*.pdf`), subject texts (`subject.en.txt`), and problem statements remain copyright 42 Network / 1337 School and are included strictly for educational, non-commercial, offline training and self-evaluation purposes.
