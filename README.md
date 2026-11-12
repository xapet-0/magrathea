# Magrathea

[![Engine](https://img.shields.io/badge/Engine-Deepthought_5--Gate-0969da.svg)](#the-5-gate-evaluation-pipeline)
[![Curriculum](https://img.shields.io/badge/Curriculum-42_%2F_1337_Coding_School-2ea44f.svg)](#curriculum-coverage-439-exercises)
[![Exercises](https://img.shields.io/badge/Exercises-439_Materialized-brightgreen.svg)](#curriculum-coverage-439-exercises)
[![Memory_Runtime](https://img.shields.io/badge/Memory-Tsoding_Arena_%2B_Redzone_Canary-8a2be2.svg)](#memory-sentinel--arena-01-telemetry)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776ab.svg)](#system-requirements)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero_External-success.svg)](#key-capabilities)
[![Platform](https://img.shields.io/badge/Platform-Linux_%7C_macOS_%7C_WSL2-informational.svg)](#system-requirements)

**Magrathea** (`v0.1.1`) is an autonomous, zero-dependency offline simulation and continuous evaluation ecosystem for the **42 and 1337 Coding School** curriculum. It delivers a hermetic, standalone implementation of **ExamShell** (`v0.1.1`), the continuous curriculum evaluator **Moulinette**, the deterministic 5-gate **Deepthought** grading harness, the **Pool Forge** (`pforge`) curriculum packager, and the official **Norminette v3** and **Shnorm v4.2** static analysis linters.

Built for zero-setup portability, offline resilience, and forensic grading parity, Magrathea ships with **439 fully materialized exercises** (`136` C Piscine + `303` Exam), **20 official curriculum PDFs**, **18 exam pool definitions**, verified reference solutions, a C11 linker-wrapped memory sentinel ([`sandbox_harness.c`](deepthought/sandbox_harness.c)) backed by [Tsoding Arena](third_party/tsoding_arena/arena.h), and an embedded pure-Python YAML runtime ([`yaml/`](yaml/)) requiring zero external package managers or internet connectivity.

---

## Table of Contents

- [Key Capabilities](#key-capabilities)
- [Quick Start](#quick-start)
- [CLI Tooling & Workflows](#cli-tooling--workflows)
  - [1. `examshell` — Authentic Cluster Examination Terminal](#1-examshell--authentic-cluster-examination-terminal)
  - [2. `moulinette` — Interactive Curriculum Navigator & Grader](#2-moulinette--interactive-curriculum-navigator--grader)
  - [3. `deepthought` — Headless 5-Gate Evaluation Engine](#3-deepthought--headless-5-gate-evaluation-engine)
  - [4. `norminette` & `shnorm` — 42 Coding Standard Linters](#4-norminette--shnorm--42-coding-standard-linters)
  - [5. `pforge` — Curriculum Pool & Exercise Packager](#5-pforge--curriculum-pool--exercise-packager)
- [The 5-Gate Evaluation Pipeline](#the-5-gate-evaluation-pipeline)
- [Memory Sentinel & Arena-01 Telemetry](#memory-sentinel--arena-01-telemetry)
- [Curriculum Coverage (439 Exercises)](#curriculum-coverage-439-exercises)
- [Makefile Targets](#makefile-targets)
- [Repository Architecture](#repository-architecture)
- [System Requirements](#system-requirements)
- [Academic Integrity & Anti-Spoiler Policy](#academic-integrity--anti-spoiler-policy)

---

## Key Capabilities

* **Zero External Dependencies (`Plug & Play`)**: Runs immediately on Python 3.8+ using only standard library modules and an embedded pure-Python YAML parser (`yaml/`). No `pip install`, virtual environments, or network access required.
* **Hermetic 5-Gate Evaluation Pipeline**: Replicates the authentic 42 grading chain:
  1. Turn-In & Entry-Point Validation (`Makefile`, header guards, forbidden `main()` detection)
  2. External Symbol Whitelist (`nm -u` against `meta.yml` `allowed_functions`)
  3. Strict Compiler Gate (`gcc`/`clang` with `-Wall -Wextra -Werror`)
  4. C11 Linker-Wrapped Memory Sentinel (`-Wl,--wrap=malloc,free,calloc,realloc,strdup,exit,_exit,_Exit`)
  5. Differential Oracle & Edge-Case Verification (`INT_MIN`, `NULL`, empty strings, out-of-bounds guards, and ASLR-safe memory dumps)
* **Complete 439-Exercise Catalog**: Every exercise includes `subject.en.txt`, `meta.yml`, `scale.yml`, comprehensive boundary/edge-case `tests.yml`, and a strict-verified reference implementation in `corrections/`.
* **Dual-Domain Memory Isolation (`Arena-01`)**: Internal harness metadata is allocated exclusively inside a dedicated Tsoding region arena (`trusted_harness/dt_arena.c`), while student heap calls (`malloc`/`calloc`/`realloc`/`strdup`/`free`) are tracked independently with 16-byte front/rear redzone canaries (`0xA5`/`0xAA`).
* **Real & Practice (`--practice`) Exam Modes**: Supports authentic cluster exam conditions (exponential Vogsphere cooldowns, bare Git repository pushes, strict trace outputs) alongside a practice mode for rapid local iteration and instant re-grading.
* **Cross-Platform Git Portability**: All 3,011 repository files adhere strictly to POSIX and Windows/WSL2/NTFS filename portability rules (`0` forbidden `*:?"<>|` characters).

---

## Quick Start

Clone the repository and run any tool directly from the project root—no installation or build step is required:

```bash
# 1. Display all available Make targets and quick commands
make help

# 2. List all 17 C Piscine modules (136 exercises) and 18 Exam pools (303 exercises)
make list

# 3. Launch the interactive Moulinette Piscine & Exam TUI/REPL
./bin/moulinette

# 4. Launch the authentic 42 / 1337 ExamShell terminal (Real Mode)
./bin/examshell

# 5. Launch ExamShell in Coaching / Practice Mode
./bin/examshell --practice
```

---

## CLI Tooling & Workflows

### 1. `examshell` — Authentic Cluster Examination Terminal

Simulates the official 42 / 1337 examination environment (`v0.1.1`) within an 80x24-compliant terminal viewport, complete with bare Vogsphere Git repositories, exponential retry cooldowns, and real-time countdown timers.

```bash
# Start a real cluster exam session
./bin/examshell

# Start a practice session (enables local check & instant re-grading)
./bin/examshell --practice

# Execute a single non-interactive command inside ExamShell
./bin/examshell -c "status"
```

**In-Session Commands:**
| Command | Mode | Description |
| :--- | :---: | :--- |
| `status` | All | Displays current level, active assignment, XP progress, Vogsphere remote path, and remaining time. |
| `subject` | All | Renders the current assignment specification (`subject.en.txt`) inside the terminal pager. |
| `grademe` | All | Validates Vogsphere push state, runs the 5-gate Deepthought pipeline on `~/rendu/<exercise>`, and writes a failure trace on `KO`. |
| `grademe --now` | Practice | Bypasses the retry cooldown timer for rapid iterative debugging in `--practice` mode. |
| `trace` | All | Displays the most recent Deepthought compiler, memory, or diff trace. |
| `clean` | All | Purges swap files (`.swp`), object files (`.o`), and stray binaries from the turn-in directory. |
| `finish` | All | Concludes the examination session and records final telemetry. |

---

### 2. `moulinette` — Interactive Curriculum Navigator & Grader

Dual-mode TUI/CLI for browsing the 439-exercise catalog, scaffolding workspaces, and grading individual exercises or entire Piscine modules.

```bash
# Launch the interactive full-screen TUI / REPL
./bin/moulinette

# List all modules, exam pools, and exercise slugs
./bin/moulinette --list

# Grade one exercise (Piscine: read from <module>/<exNN>/, see "The 42 way" below)
./bin/moulinette ft_split

# Grade a Piscine module or exercise with strict Norminette + Memory Sentinel checks
./bin/moulinette c07

# Continuously watch and re-grade an exercise whenever source files change
./bin/moulinette --watch ft_strjoin
```

**The 42 way.** Nothing is prepared for you: you read the subject where it is, you create the turn-in folders yourself, and the grader reads exactly what the subject names (`Turn-in directory: ex00/`).

```bash
ls subjects/piscine/c00/                               # the assignments of the module
cat subjects/piscine/c00/ft_putchar/subject.en.txt     # the subject
mkdir -p workspace/piscine/c00/ex00                    # your folders, made by you
vim workspace/piscine/c00/ex00/ft_putchar.c            # your code
./bin/moulinette ft_putchar                            # one exercise
./bin/moulinette c00                                   # the whole module, ex00 upwards
```

The module folder can live anywhere, like a cloned repository (`~/piscine/c00/ex00/ft_putchar.c`): run the grader from that folder, from one of its `exNN` folders, or from the folder that contains it. From anywhere else it reads `workspace/piscine/<module>/`.

`subject <exercise>` (prints the subject and the turn-in path) and `init <exercise>` (creates the folder with an empty file) are optional shortcuts; grading never depends on them.

Rules the grader applies to what you type:

* **Names are exact.** No partial match, no wildcard, no `..`. `strlen` is not `ft_strlen`.
* **A shared name is never guessed.** A bare name goes to the Piscine first (`--exam` flips it) and a one-line note lists the namesakes. When two modules have an equal claim (`ft_putnbr` in `c00` and `c04`) the name is refused: write `c04/ft_putnbr`.
* **Turn-in location.** `--dir <path>`, else the exercise folder you stand in, else `<module>/<exNN>/` for the Piscine and `workspace/exams/<exercise>/` for exam exercises. A file left in another `exNN` is not turned in. The current directory is never graded wholesale.
* **Your folders are yours.** Grading and `watch` create no folder. "Nothing turned in" names the folder and the file that were expected.
* **XP is earned once per exercise** in `workspace/xp_ledger.json`. An alternative `--xp-ledger`, `--self-test` and `--json` never credit the student profile.
* **The full trace of the last grading** is kept in `workspace/traces/`; inside the TUI, `trace` opens it in `$PAGER` (the full-screen view has no scrollback).
* **Reference solutions and hints stay locked.** Read the subject, read the trace.

---

### 3. `deepthought` — Headless 5-Gate Evaluation Engine

Low-level command-line interface to the grading engine for direct directory evaluation, automated scripts, and CI pipelines.

```bash
# Grade a specific submission directory against an exercise slug
./bin/deepthought grade piscine/c07/ft_split --dir workspace/rendu/ft_split

# Grade an exam exercise in strict mode
./bin/deepthought grade exams/flood_fill --dir workspace/rendu/flood_fill --exam --strict

# Inspect engine status and runtime configuration
./bin/deepthought status
```

---

### 4. `norminette` & `shnorm` — 42 Coding Standard Linters

`bin/norminette` **is the official 42 norminette** ([42school/norminette](https://github.com/42school/norminette), MIT), shipped unmodified in [`third_party/norminette/`](third_party/norminette/). The grader's `Norme error` is its verdict, so code that passes here passes at school. `bin/shnorm` is Magrathea's own **Sh-Norm v4.2** linter for POSIX shell scripts.

```bash
# The official norminette: same options, same output as at school
./bin/norminette workspace/
./bin/norminette corrections/piscine/c07/ft_split/ft_split.c
./bin/norminette -R CheckDefine ft_abs.h      # the rule a C 08 subject names
./bin/norminette --version

# Lint POSIX shell scripts against Sh-Norm v4.2
./bin/shnorm bocal/*.sh bin/*.sh
```

* **Nothing to install, on any system.** The tool is pure Python and lives in the repository: no `pip`, no virtual environment, no distribution package, no network. It runs wherever Python 3.10 or newer runs (Debian, Fedora, Arch, Void, Alpine, NixOS, macOS, WSL). `./install.sh` puts `norminette` on your `PATH` and prints the version in use.
* **Python older than 3.10.** The official tool cannot run on it. The kit looks for a newer `python3.x` on `PATH`; when there is none it uses a small built-in checker (header, 80 columns, 25 lines, 5 functions, 4 parameters, forbidden keywords) and **says so in every trace**: `norminette: built-in checker, a part of the Norm only`. Install Python 3.10+ to get the school's verdict. `MAGRATHEA_NORMINETTE=builtin` forces the built-in checker.
* **`-R CheckDefine`.** A subject that names this rule (C 08 `ft_abs.h`, `ft_boolean.h`: a macro with arguments is the exercise) is graded with it: `norminette_rule: CheckDefine` in its `meta.yml`.
* **Another version.** `python3 third_party/update_norminette.py 3.3.60` fetches the wheel published on PyPI by 42school, checks its sha256 and replaces the shipped copy. Then run `python3 tests/test_norminette_official.py`: it checks every Piscine reference solution and every file `init` writes against the new version.
* **Exam mode.** As at school, exams are not norm-checked unless you ask (`--norm`). The exam reference solutions are not written to the Norm.

---

### 5. `pforge` — Curriculum Pool & Exercise Packager

Utility for scaffolding new exercises, validating pool YAML schemas, and exporting sanitized student distribution packages (automatically stripping `corrections/` and internal grading answers).

```bash
./bin/pforge --help
```

---

## The 5-Gate Evaluation Pipeline

Every student submission is evaluated sequentially through five isolated stages in [`deepthought/grader.py`](deepthought/grader.py). Failure at any stage halts execution immediately and emits the corresponding diagnostic status:

| Gate | Stage | Mechanism | Diagnostic Verdicts |
| :---: | :--- | :--- | :--- |
| **1** | **Turn-In, Norm & Repository Gate** | Verifies expected filenames, rejects symlinks and forbidden files, checks `Makefile` rules (`all`, `clean`, `fclean`, `re`, relink guard) via [`makefile_and_repo.py`](deepthought/makefile_and_repo.py), and runs `norminette` / `shnorm`. | `Nothing turned in` / `Norme KO` / `Makefile KO` |
| **2** | **AST & Symbol Whitelist Gate** | Scans C/C++ sources for forbidden `#include` directives or unauthorized `main()` definitions, then inspects compiled object files via `nm -u` against `allowed_functions` in `meta.yml`. | `Cheating (-42)` / `Forbidden function` |
| **3** | **Strict Compilation Gate** | Compiles student sources alongside the generated test harness under `-Wall -Wextra -Werror` inside an isolated temporary build directory. | `Does not compile` |
| **4** | **Sandbox & Memory Sentinel Gate** | Executes the binary inside an isolated environment (mode-`000` `/tmp` masking when `unshare -Urm` is available, resource limits `RLIMIT_AS`/`RLIMIT_CPU`/`RLIMIT_NPROC`, and linker-wrapped heap sentinels). | `Timeout` / `Segfault` / `Bus error` / `Abort` / `Leak KO` / `Redzone KO` / `Double Free KO` / `Forbidden Exit KO` |
| **5** | **Differential & Edge-Case Oracle** | Runs all named fixed and oracle test vectors from `tests.yml`, comparing `stdout`, `stderr`, exit status, and mutated in-memory state against expected specifications. | `KO :(` / `OK :)` (`100/100`) |

---

## Memory Sentinel & Arena-01 Telemetry

Magrathea's C11 runtime harness ([`deepthought/sandbox_harness.c`](deepthought/sandbox_harness.c) and [`trusted_harness/`](trusted_harness/)) enforces strict separation between harness allocations and student heap memory using GNU ld symbol wrapping (`-Wl,--wrap=malloc,free,calloc,realloc,strdup,exit,_exit,_Exit`):

| Exit / Signal Code | Diagnostic Status | Condition Trapped by `sandbox_harness.c` |
| :---: | :--- | :--- |
| **`0`** | `OK :)` | All test vectors passed with zero leaked blocks and intact redzone canaries. |
| **`42`** | `Leak KO` | Student code left unfreed heap blocks at function return (`student_leaked_blocks > 0`). |
| **`43`** | `Redzone KO` | Student code overwrote the 16-byte front (`0xA5`) or rear (`0xAA`) heap canary guard. |
| **`44`** | `Double Free KO` | Student code called `free()` on an untracked, unaligned, or already-freed pointer (`0xDD`). |
| **`45`** | `Forbidden Exit KO` | Student function invoked `exit()`, `_exit()`, or `_Exit()` directly while `g_dt_in_student_call == 1` (unless `exit` is listed in `allowed_functions`). |
| **`-6` / `-11`** | `Abort` / `Segfault` | Process terminated by `SIGABRT` (`-6`) or `SIGSEGV` (`-11`) — distinct from normal exit code `6`. |

---

## Curriculum Coverage (439 Exercises)

All **439 exercises** are materialized under [`subjects/`](subjects/) and paired with strict-verified reference solutions under [`corrections/`](corrections/):

### 1. C Piscine — 17 Modules (`136` Exercises)
| Module | Topic | Exercises | Official PDF |
| :--- | :--- | :---: | :--- |
| `shell00` | UNIX Shell & Git Essentials | `10` | `subjects/piscine/shell00/shell00.en.pdf` |
| `shell01` | Shell Scripting & Pipelines | `8` | `subjects/piscine/shell01/shell01.en.pdf` |
| `c00` | First Steps in C (`write`, loops, combinations) | `9` | `subjects/piscine/c00/c00.en.pdf` |
| `c01` | Pointers, Dereferencing & Array Sorting | `9` | `subjects/piscine/c01/c01.en.pdf` |
| `c02` | Strings, Buffers & Memory Hex Dump (`ft_print_memory`) | `13` | `subjects/piscine/c02/c02.en.pdf` |
| `c03` | String Comparison, Concatenation & Search (`<string.h>`) | `6` | `subjects/piscine/c03/c03.en.pdf` |
| `c04` | Number Formatting & Base Conversion (`ft_atoi_base`, `ft_putnbr_base`) | `6` | `subjects/piscine/c04/c04.en.pdf` |
| `c05` | Recursion, Factorials, Primes & `N`-Queens (`ft_ten_queens_puzzle`) | `9` | `subjects/piscine/c05/c05.en.pdf` |
| `c06` | Command-Line Arguments (`argc` / `argv`) | `4` | `subjects/piscine/c06/c06.en.pdf` |
| `c07` | Dynamic Memory Allocation (`malloc`, `ft_split`, `ft_convert_base`) | `6` | `subjects/piscine/c07/c07.en.pdf` |
| `c08` | Preprocessor Macros, Structs & Header Files (`.h`) | `6` | `subjects/piscine/c08/c08.en.pdf` |
| `c09` | Static Libraries (`libft.a`) & `Makefile` Automation | `3` | `subjects/piscine/c09/c09.en.pdf` |
| `c10` | File Descriptors & UNIX Utilities (`ft_display_file`, `ft_cat`, `ft_tail`, `ft_hexdump`) | `4` | `subjects/piscine/c10/c10.en.pdf` |
| `c11` | Function Pointers & Higher-Order Array Operations | `8` | `subjects/piscine/c11/c11.en.pdf` |
| `c12` | Singly Linked Lists (`t_list` creation, sorting, removal, merging) | `18` | `subjects/piscine/c12/c12.en.pdf` |
| `c13` | Binary Search Trees (`t_btree` traversals, level-order, apply) | `8` | `subjects/piscine/c13/c13.en.pdf` |
| `rush_bsq` | Team Rushes (`rush00`–`rush02`) & Capstone `bsq` | `9` | `subjects/piscine/rush_bsq/*.en.pdf` |

### 2. Cluster Examinations — 18 Pool Definitions (`303` Unique Exercises)
* **C Piscine Exams (1337 & 42 Classic)**: `c_piscine_exam_00`, `c_piscine_exam_01`, `c_piscine_exam_02`, `c_piscine_final_exam`, `1337_classic_exam00`–`examfinal`.
* **Common Core Cursus Ranks**: `rank02` (`get_next_line`, `ft_printf`, `union`, `inter`, `flood_fill`), `rank03` (`mini_paint`, `micro_paint`), `rank04` (`microshell`), `rank05` (`cpp_module_00`–`02`, `bigint`, `polyset`, `vect2`), `rank06` (`mini_serv`, `mini_db`), plus `new_2026_exam`, `classic_42_full`, `cursus_rank03_06`, `piscine_reloaded`, and `day09`.

---

## Makefile Targets

```bash
make help       # Show quick-reference banner and available commands
make list       # Display all 17 C Piscine modules and Exam pools
make piscine    # Launch interactive Moulinette curriculum explorer
make exam       # Launch interactive 42 / 1337 ExamShell (Real Mode)
make practice   # Launch interactive ExamShell in Coaching / Practice Mode
make norm       # Run 42 Norminette v3 on workspace/
make shnorm     # Run POSIX Shell Norm v4.2 on bocal/*.sh and bin/*.sh
make clean      # Clean temporary workspace artifacts, traces, and bytecode caches
```

---

## Repository Architecture

```text
magrathea/
├── bin/                        # First-party CLI executables
│   ├── examshell               # Interactive 42 / 1337 examination terminal (v0.1.1)
│   ├── moulinette              # Curriculum navigator, workspace scaffolder & grader
│   ├── deepthought             # Headless 5-gate evaluation CLI
│   ├── norminette              # Runs the official norminette in third_party/ (built-in fallback)
│   ├── shnorm                  # POSIX Shell Norm v4.2 static analyzer
│   ├── pforge                  # Curriculum pool & exercise packager
│   ├── ft_lock                 # Cluster session screen locker
│   └── libmemsentinel.so       # Prebuilt shared memory sentinel library
├── bocal/                      # Cluster administration, PAM, and workstation scripts
├── corrections/                # Verified reference solutions for all 439 exercises
│   ├── exams/                  # 303 Exam reference implementations
│   └── piscine/                # 136 C Piscine reference implementations
├── deepthought/                # Core Python grading engine & C11 sandbox harness
│   ├── grader.py               # 5-gate evaluation pipeline & harness code generator
│   ├── sandbox_harness.c       # Linker-wrapped heap canary, leak & exit trap harness
│   ├── makefile_and_repo.py    # Makefile target/relink verifier & repository hygiene checks
│   ├── shnorm_engine.py        # POSIX Shell Norm v4.2 validator
│   ├── vogsphere.py            # Local bare Git repository & exponential cooldown manager
│   ├── progression.py          # Student XP ledger, rank progression & profile manager
│   ├── pool_forge.py           # Exercise scaffolder & student package exporter
│   └── ui_theme.py             # 80x24 ANSI/VT100 terminal viewport renderer
├── docs/                       # Architecture & 5-Gate technical specifications
├── pools/                      # 17 Piscine module catalogs & 18 Exam pool YAML manifests
├── schemas/                    # Validation schemas for subjects, pools, and profiles
├── subjects/                   # 439 exercise directories (subject.en.txt, meta.yml, scale.yml, tests.yml, PDFs)
├── templates/                  # Exercise, scale, and profile YAML templates
├── third_party/
│   ├── norminette/             # The official 42 norminette, unmodified (MIT); see SOURCE.txt
│   ├── update_norminette.py    # Fetch another norminette version from PyPI (sha256 checked)
│   └── tsoding_arena/          # Embedded Tsoding region arena allocator (arena.h)
├── trusted_harness/            # C11 trusted harness diagnostics & Arena-01 telemetry
│   ├── dt_arena.c / .h         # Internal harness arena lifecycle & telemetry collector
│   ├── dt_diagnostics.c / .h   # Deterministic exit-status & signal classifier
│   └── dt_sandbox_harness.h    # Linker-wrap & redzone canary interface
├── vogsphere/                  # Runtime bare Git repository storage (.gitkeep)
├── workspace/                  # Student turn-in workspace (rendu/, subject/, exams/)
├── yaml/                       # Embedded pure-Python YAML parser (zero external dependencies)
├── Makefile                    # Master user & curriculum Makefile
└── README.md                   # Platform documentation
```

---

## System Requirements

* **Operating System**: Linux (`x86_64` / `aarch64`), macOS, or Windows WSL2.
* **Python Runtime**: Python `3.8+` (standard library only; zero `pip` packages required). The official norminette needs Python `3.10+`; on an older Python the norm check falls back to a built-in checker that covers a part of the Norm and says so.
* **Compilers**: `gcc` or `clang` (with `g++` / `clang++` for Rank 05 C++ exercises).
* **Standard UNIX Toolchain**: `git`, `make`, `nm`, `ar`, `sh`, `diff`.

---

## Academic Integrity & Anti-Spoiler Policy

Reference implementations in [`corrections/`](corrections/) exist strictly as internal differential oracles for Gate 5 grading verification. Magrathea enforces a multi-layer anti-spoiler policy:
1. **CLI & REPL Spoiler Lock**: Commands and flags requesting solution or hint disclosure (`solve`, `solution`, `--solve`, `--solution`, `hint`, `--hint`) are permanently locked across both real and `--practice` modes (returning exit code `2`).
2. **Sandbox Filesystem Masking**: During exercise execution, `/tmp` is masked with an empty `mode 000` `tmpfs` inside an unprivileged mount namespace (`unshare -Urm`) whenever supported by the host kernel, and C/C++ sources are scanned pre-compilation to block unauthorized `#include` path traversal.
3. **Diagnostic-Driven Learning**: Students resolve `KO` verdicts exclusively through compiler output, memory sentinel telemetry (`Leak KO`, `Redzone KO`), and unified output diffs.
