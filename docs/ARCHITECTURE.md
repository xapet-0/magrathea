# Magrathea Architecture Specification

## 1. Overview

**Magrathea** is a lightweight, self-contained, standalone implementation of the official **42 / 1337 Coding School Evaluation and Examination Ecosystem**. It provides a fully autonomous, offline-capable environment containing the classic **ExamShell** (`examshell`), the automated continuous grader **Moulinette** (`moulinette`), the core evaluation engine **Deepthought** (`deepthought`), and official coding standard linters **Norminette** (`norminette`) and **Shnorm** (`shnorm`).

The entire repository requires zero external package managers or network dependencies. It runs directly on POSIX-compliant environments (Linux, macOS, FreeBSD).

---

## 2. Directory Structure

```text
magrathea/
├── README.md               # User onboarding guide and quickstart reference
├── Makefile                # Build and execution targets
├── install.sh              # System dependency check and ~/.local/bin symlink installer
├── examshell -> bin/examshell
├── moulinette -> bin/moulinette
├── bin/                    # First-party CLI binaries and helper tools
│   ├── moulinette          # Interactive Moulinette REPL & batch exercise grader
│   ├── examshell           # Timed ExamShell REPL simulation with Vogsphere git push
│   ├── deepthought         # Low-level 5-gate grading runner
│   ├── norminette          # 42 Norm v3 static C code analyzer
│   ├── shnorm              # 42 Shell script style & security linter
│   ├── pforge              # Pool & subject scaffolding utility
│   ├── ft_lock             # Session lock file utility
│   └── ...
├── bocal/                  # Cluster workstation scripts (Bocal administration)
├── deepthought/            # Core Python & C11 grading engine & UI subsystems
│   ├── compiler_and_symbols.py  # ELF nm -u symbol gate & compiler invocations
│   ├── grader.py                # 5-gate grading orchestrator & namespace sandbox
│   ├── sandbox_harness.c        # Malloc redzone canary & leak detector wrapper
│   ├── ui_theme.py              # 4-palette terminal theme engine
│   ├── vogsphere.py             # Bare Git repository management
│   └── ...
├── trusted_harness/        # C11 Arena-01 adapter & compiler/leak guards
│   ├── dt_arena.c          # mmap-backed dual-domain arena allocator
│   ├── dt_compiler_guard.c # Include restriction pre-scanner
│   └── dt_sandbox_harness.h
├── third_party/            # Bundled upstream components
│   ├── norminette/         # Official 42 Norminette (3.3.60)
│   └── tsoding_arena/      # arena.h mmap region allocator with PROT_NONE guard page
├── docs/                   # Technical specifications
│   ├── ARCHITECTURE.md     # This architecture reference
│   └── CORE_ENGINE_5_GATES.md
├── pools/                  # Curriculum tracks and examination definitions (YAML)
│   ├── exams/              # 9 Exam tracks (Rank 02-06, C Piscine Exam 00-02, Final)
│   └── piscine/            # 17 C Piscine modules (Shell 00 to C 13, Rush/BSQ)
├── subjects/               # 439 Canonical exercise subjects
│   ├── exams/              # 303 exam exercises
│   └── piscine/            # 136 piscine exercises (including 20 official PDFs)
├── corrections/            # Reference solutions for all 439 exercises
├── schemas/                # JSON/YAML validation schemas
├── templates/              # Pool, scale, and profile templates
├── vogsphere/              # Local bare git repository simulation
└── workspace/              # Student work area
    ├── rendu/              # Default turn-in folder for code submissions
    └── subject/            # Current exercise subject folder in ExamShell
```

---

## 3. The 5-Gate Grading Pipeline

Deepthought subjects student submissions through an unyielding 5-gate pipeline:

```mermaid
flowchart LR
    A["Turn-in Code"] --> G1["Gate 1: Norminette"]
    G1 -->|"Pass"| G2["Gate 2: Symbol Whitelist"]
    G1 -->|"Fail"| F["Grading Trace: KO"]
    G2 -->|"Pass"| G3["Gate 3: GCC/Clang -Werror"]
    G2 -->|"Fail"| F
    G3 -->|"Pass"| G4["Gate 4: Canary Redzone"]
    G3 -->|"Fail"| F
    G4 -->|"Pass"| G5["Gate 5: Differential Diff"]
    G4 -->|"Fail"| F
    G5 -->|"Pass"| P["Result: 100% OK"]
    G5 -->|"Fail"| F
```

1. **Gate 1: Norminette (`norminette`)**:
   - Enforces the 42 C Coding Standard (4-space tabs, max 25 lines per function, max 5 functions per file, max 4 parameters, forbidden control structures like `for`, `do..while`, `switch`, `goto`).
   - Flags forbidden single-line comments (`//`), unaligned variable declarations, and missing official 42 headers.

2. **Gate 2: Symbol Whitelist (`compiler_and_symbols.py`)**:
   - Compiles an unlinked object file and executes `nm -u` to extract all external referenced symbols.
   - Enforces exact function whitelists specified in the exercise's `meta.yml` (e.g., rejecting any unauthorized call to `printf`, `malloc`, or `exit`).

3. **Gate 3: Strict Compilation (`gcc` & `clang`)**:
   - Evaluates submission against `-Wall -Wextra -Werror` using dual-compiler verification.
   - Flags unused variables, implicit function declarations, and incompatible type assignments.

4. **Gate 4: Runtime Sandbox & Canary Redzone (`sandbox_harness.c`)**:
   - Masks `corrections/`, `subjects/`, and `pools/` inside an unprivileged Linux user/mount namespace (`CLONE_NEWUSER | CLONE_NEWNS` + `mode=000` `tmpfs`) when permitted by the host kernel, while keeping build temp directories writable.
   - Interposes memory allocations on Linux/WSL2 (`GNU ld`) via `-Wl,--wrap=malloc,calloc,realloc,reallocarray,strdup,strndup,free,read,exit,_exit,_Exit` (gracefully omitted on macOS `ld64`).
   - Surrounds heap allocations with 16-byte front (`0x5A`) and 16-byte rear (`0xA5`) redzone canaries, while isolating harness metadata in `trusted_harness/dt_arena.c` (`mmap` regions with trailing `PROT_NONE` guard pages).
   - Detects buffer underflows/overflows (`43`), invalid/arena frees (`44`), allocation cap exhaustion (`45`), double frees (`6`), and unfreed heap blocks at termination (`42`).

5. **Gate 5: Differential Output Oracle (`grader.py`)**:
   - Compares standard output and return codes against verified reference implementations in `corrections/`.
   - Evaluates edge cases: empty strings, boundary integers (`INT_MIN`, `INT_MAX`), unaligned buffers, and malformed command-line inputs.

---

## 4. Key CLI Binaries

- **`examshell`**: Interactive terminal application replicating the authentic 42 examination environment. Manages exam timers, dynamic exercise assignments across difficulty levels, automatic folder generation in `~/rendu`, and grading via `grademe` with simulated Vogsphere Git pushes.
- **`moulinette`**: Fast, dual-mode curriculum explorer and grader. Supports direct single-exercise grading (`./bin/moulinette ft_strlen`), exercise scaffolding (`./bin/moulinette --init ft_strlen`), subject viewing (`./bin/moulinette subject ft_strlen`), and continuous file-watching (`./bin/moulinette --watch ft_strlen`).
- **`deepthought`**: Direct command-line interface to the 5-gate grader. Used for batch headless evaluations and scripted CI pipelines.
- **`norminette`**: Standalone 42 Norm compliance checker.
- **`shnorm`**: POSIX-compliant shell script style, quoting, and security auditor.
