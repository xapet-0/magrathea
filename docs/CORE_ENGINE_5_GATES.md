# 42 / 1337 Deepthought Moulinette — 5-Gate Engine Architecture & Core Specification

> **Document Status**: Production Systems Architecture Specification  
> **Target Engine**: 5-Gate Evaluation & Adversarial Sandboxing System  
> **Source Modules**: `deepthought/grader.py`, `deepthought/compiler_and_symbols.py`, `deepthought/sandbox_harness.c`, `trusted_harness/dt_arena.c`

---

## 1. The 5 Evaluation Gates & Exit Codes

Moulinette and Deepthought evaluate every submission sequentially through a 5-gate pipeline. Failure at any gate immediately halts grading and reports a deterministic status:

| Gate | Name | Trigger / Command | Exit / Signal Code |
| :--- | :--- | :--- | :--- |
| **Gate 1** | Style, Files & Norm | Turn-in layout, Makefile rules, `norminette` / `shnorm` | `Nothing turned in` / `Norme KO` / `Makefile KO` |
| **Gate 2** | Symbol Inspection | Include/splice/asm scan + `nm -u` whitelist filter | `Cheating (-42)` / `Forbidden function` |
| **Gate 3** | Strict Compilation | `cc -Wall -Wextra -Werror` (dual `gcc`+`clang` under `--strict`) | `Does not compile` |
| **Gate 4** | Memory & Sandboxing | C11 Memory Sentinel (`0x5A`/`0xA5` redzones) + Arena-01 + rlimits | `42` (Leak), `43` (Redzone), `44` (Invalid/Arena Free), `45` (Cap), `6` (Double Free) |
| **Gate 5** | Differential & Edge Oracle | Fixed, boundary, and oracle diffing (`diff -U 3` / `cat -e`) | `Diff KO :(` / `OK :)` |

---

## 2. Memory Isolation & Canary Sandboxing

On Linux and WSL2 (`GNU ld`), student binaries are statically linked against `deepthought/sandbox_harness.c` using `-DDT_WRAP_MALLOC` and GNU linker symbol wrapping (`-Wl,--wrap=malloc,calloc,realloc,reallocarray,strdup,strndup,free,read,exit,_exit,_Exit`). On macOS (`darwin` Apple `ld64`), `-Wl,--wrap` is omitted gracefully and evaluation runs through Gates 1–3 and Gate 5 (`rlimit` + session-group isolation).

Every dynamic allocation is bounded by 16-byte front and rear redzones filled with distinct asymmetric canary patterns:

```c
#define DT_LEFT_REDZONE_SIZE 16
#define DT_RIGHT_REDZONE_SIZE 16
#define DT_LEFT_CANARY 0x5A
#define DT_RIGHT_CANARY 0xA5
```

### Allocation Lifecycle
1. **Padded Allocation**: `malloc`/`calloc`/`realloc`/`reallocarray`/`strdup`/`strndup` wrappers allocate `16 + size + 16` bytes, stamping `0x5A` before the user pointer and `0xA5` immediately after `size` bytes.
2. **Dual-Domain Arena Separation**: Tracking nodes (`t_alloc_node`) and harness scratch buffers live inside `trusted_harness/dt_arena.c` (`mmap`-backed `ARENA_BACKEND_LINUX_MMAP` regions terminated by a trailing `mprotect(..., PROT_NONE)` hardware guard page), completely isolated from the wrapped libc student heap.
3. **Free & Double-Free Validation**: `__wrap_free` checks arena ownership (Exit `44`), untracked/misaligned pointers (Exit `44`), inactive/double-freed nodes (`[DOUBLE FREE KO]`, Exit `6`), and redzone integrity (Exit `43`).
4. **Termination Audit (`on_exit` / `__wrap_exit` / `__wrap__exit` / `__wrap__Exit`)**: At process termination, remaining active nodes are checked for redzone corruption (Exit `43`) and unfreed blocks (Exit `42` when `DT_CHECK_LEAKS=1` and exit status is `0`).

---

## 3. Core Engine Source Components

1. **`deepthought/grader.py`**: 5-gate pipeline orchestrator, YAML schema/depth/size validator (`_safe_load_yaml`), Linux user/mount namespace isolation (`unshare(CLONE_NEWUSER | CLONE_NEWNS)` masking `corrections/`, `subjects/`, `pools/` with `mode=000` `tmpfs` when permitted by the host kernel), POSIX `rlimit` enforcement, and differential test runner.
2. **`deepthought/compiler_and_symbols.py`**: Pre-scan for line-spliced directives (`\\\n`), forbidden `#include` paths, unauthorized `main()`, inline assembly (`asm`/`__asm__`), `nm -u` undefined symbol extraction, and strict compilation (`FLAGS_COMPILE_SAFE`).
3. **`deepthought/sandbox_harness.c`**: Thread-safe (`_Thread_local` recursion guard + atomic spinlock) memory interceptor, `DT_FAIL_MALLOC_AT` OOM fault injector, `DT_CHUNK_READ=1` partial-read tester, and Arena-01 JSONL telemetry emitter.
4. **`trusted_harness/dt_arena.c` & `third_party/tsoding_arena/arena.h`**: Overflow-guarded anonymous `mmap` arena allocator with epoch-validated mark/rewind and trailing hardware `PROT_NONE` guard pages.

---

## 4. Verification & Testing

```bash
make check    # Verify host toolchain and Python 3.10+
make shnorm   # Audit all POSIX shell scripts
make norm     # Run official 42 Norminette on workspace/
make test     # Execute the full Python & C unittest suite
```
