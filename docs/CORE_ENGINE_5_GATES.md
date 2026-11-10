# 42 / 1337 Deepthought Moulinette — 5-Gate Engine Architecture & Core Specification

> **Document Status**: Production Systems Architecture Specification  
> **Target Engine**: Native C 5-Gate Evaluation & Adversarial Sandboxing System  
> **Source Directory**: `core/` (`src/sandbox.c`, `src/memsentinel.c`, `src/deepthought_diff.c`, `include/moulinette_core.h`)

---

## 1. The 5 Evaluation Gates & Exit Codes

Moulinette grades every submission through an irreversible 5-gate pipeline. Failure at any gate immediately aborts grading with a specific diagnostic code:

| Gate | Name | Gate Mask | Trigger / Command | Exit / Signal Code |
| :--- | :--- | :--- | :--- | :--- |
| **Gate 1** | Style & Norm | `0x01` (`GATE_1_STYLE`) | `norminette` / `shnorm` | Exit `2` (`EXIT_GATE_STYLE_ERR`) |
| **Gate 2** | Symbol Inspection | `0x02` (`GATE_2_SYMBOLS`) | `nm -u` symbol extraction & whitelist filter | Exit `214` (`EXIT_GATE_CHEAT_U8`, `-42`) |
| **Gate 3** | Strict Compilation | `0x04` (`GATE_3_COMPILE`) | `gcc -Wall -Wextra -Werror -std=c99` | Exit `3` (`EXIT_GATE_COMPILE_ERR`) |
| **Gate 4** | Memory & Sandboxing | `0x08` (`GATE_4_SANDBOX_MEM`) | Canary Redzone + Leak Tracking + Watchdog | Exit `43` (Leak), `44` (Canary), `124` / `137` (Timeout) |
| **Gate 5** | Deepthought Adversarial | `0x10` (`GATE_5_DEEPTHOUGHT`) | 6 Mutation Modes (Boundary, Empty, Huge, Overflow) | Exit `1` (`EXIT_GATE_KO`), `0` (`EXIT_GATE_OK`) |

---

## 2. Memory Isolation & Canary Sandboxing

The sandbox surrounds every dynamic heap allocation with protective leading and trailing redzone boundaries filled with canary byte `0xAA`:

```c
#define DT_CANARY_BYTE 0xAA
#define DT_CANARY_SIZE 16

typedef struct s_canary_header {
    size_t          size;
    unsigned char   lead_canary[DT_CANARY_SIZE];
} t_canary_header;
```

### Allocation Lifecycle
1. **Padded Allocation**: `malloc(size)` is interposed via `dlsym(RTLD_NEXT)` or `-Wl,--wrap=malloc`. The actual allocation requests `sizeof(t_canary_header) + size + DT_CANARY_SIZE`.
2. **Canary Stamping**: The 16-byte leading canary and 16-byte trailing canary are initialized to `0xAA`.
3. **Guard Verification on `free()`**: Before deallocation, both guards are verified. If any byte diverges from `0xAA`, a buffer underflow or overflow is flagged immediately, triggering exit code `44`.
4. **Termination Sentinel**: At child process exit, active allocations in the tracking table are inspected. If any unfreed pointers remain, exit code `43` is emitted with exact byte counts.

---

## 3. Core Engine Source Components

The native C engine is located under `core/`:

### 1. `core/include/moulinette_core.h`
Defines the bitmasks for the five gates (`GATE_1_STYLE` through `GATE_5_DEEPTHOUGHT`), the 6 mutation modes (`t_mutation_mode`), IPC pipe structures (`t_ipc_pipes`), memory tracking and canary counters, and test vector specifications.

### 2. `core/src/sandbox.c`
Implements process isolation, signal trapping, and timeout management:
* Isolates each test inside a dedicated child process via `fork()` and `waitpid()`.
* Enforces a 2.0-second execution timeout via `setitimer(ITIMER_REAL)` and clean `SIGKILL` termination.
* Traps asynchronous signals (`SIGSEGV`, `SIGBUS`, `SIGABRT`, `SIGFPE`, `SIGILL`) and translates them to deterministic diagnostic status codes.
* Intercepts standard output via non-blocking pipes with unbuffered I/O (`_IONBF`).

### 3. `core/src/memsentinel.c`
Provides deterministic memory interception and redzone canary validation:
* Intercepts `malloc`, `calloc`, `realloc`, and `free` via `dlsym(RTLD_NEXT)`.
* Injects simulated allocation failures when `DT_FAIL_MALLOC_AT` is set to test error handling.
* Detects off-by-one heap overflows, double frees, and memory leaks.

### 4. `core/src/deepthought_diff.c`
Performs differential output matching:
* Replicates the exact behavior of `diff -U 3 user.out expected.out | cat -e` with trailing `$` markers on every line.
* Supports raw binary/hex memory comparison for byte-oriented assignments (`ft_bzero`, `ft_memset`, `ft_memcpy`).
* Generates official `.trace` execution logs.

### 5. `core/bocal/matrix_sweep_runner.c`
Master verification runner executing all 6 mutation scenarios against the 5-gate pipeline:
* `[M0]` Reference Solution Pass: `exit=0`, leaked bytes: `0B`.
* `[M1]` Corrupted Output Diff: Caught by differential oracle (`diff -U 3 | cat -e`).
* `[M2]` Deliberate NULL Dereference: Trapped as `SIGSEGV` (`exit 139`).
* `[M3]` Forbidden Symbol Invocation: Detected by `nm -u` whitelist gate (`exit 214`, cheat `-42`).
* `[M4]` Infinite Loop: Terminated cleanly by watchdog timer (`SIGALRM` / `SIGKILL`).
* `[M5]` Redzone Canary Overwrite: Detected by 1-byte heap guard check (`exit 44`).
* Emits JSON telemetry report to `build/VERIFICATION_SWEEP_REPORT.json`.

---

## 4. Verification & Testing

To compile and execute the complete native verification matrix:

```bash
# Compile core libraries and binaries
make -C core all

# Execute the 6-mutation telemetry sweep
make -C core sweep

# Clean build artifacts
make -C core clean
```
