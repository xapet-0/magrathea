# 42 / 1337 Systems Engineering, Pedagogical Architecture & Exercise Design Specification

---

## 1. The Core Divergence Across the Three Engineering Tiers

To understand the system artifacts—ranging from Bocal cluster scripts to the automated grading pipeline (**Moulinette / Deepthought**) and peer evaluation scales (**1337HUB**)—one must recognize that 42/1337 system architects strictly separate concerns across **three distinct engineering tiers**, each governed by its own invariants:

| Engineering Tier | System Archetypes | Primary Engineering Objective | Implementation Philosophy & Coding Standard |
| :--- | :--- | :--- | :--- |
| **1. Cluster Infrastructure (Bocal Cluster Ops)** | `login-user`, `ft_lock`, `goinfre_setup`, `home_reset`, `radio_off`, `unminimize` | Manage hundreds of stateless cluster workstations (Linux/macOS), isolate ephemeral volumes (`goinfre` / `sgoinfre`), and enforce physical session security (`ft_lock`). | **Pragmatic, Defensive SysAdmin Bash:** Strict `set -e`, explicit UID verification (`EUID -ne 0`), hardware and PAM state queries (`loginctl`, `xrandr`, `zfs`/`lvm`), and atomic locking primitives. |
| **2. Deterministic Automated Evaluation (Moulinette / Deepthought / ExamShell)** | `grader.py`, `sandbox_harness.c`, `auto_correc_main.sh`, `examshell` | Execute black-box and white-box verification in hermetic sandboxes without human intervention, surfacing every memory corruption and edge case. | **Deterministic Adversarial C/Python/POSIX sh:** Sequential gating (Norminette -> ELF Symbol Whitelist `nm -u` -> Redzone Canary `0xA5` -> `-ftrapv` -> Output Diff -> Watchdog SIGKILL). |
| **3. Interactive Peer Defense (1337HUB Peer-Evaluation Scale)** | Project defense sheets (e.g. `Born2beroot`) | Verify deep conceptual comprehension, verbal defense, and **Live Mutation Defense** in the presence of an evaluator to eliminate plagiarism or AI hallucination. | **Strict Interactive Audit Protocol:** Stop-on-first-failure gates, cryptographic hash verification (`signature.txt` vs `.vdi`), and live runtime parameter modifications. |

---

## 2. Forensic Analysis of 1337HUB Peer-Evaluation Protocols

The evaluation protocols in 1337HUB represent a live systems audit specification designed around three adversarial checks:

### A. Single Source of Truth & Clean Environment
1. **Official Git Repository as Single Source of Truth:**
   - *"Only grade the work that was turned in the Git repository of the evaluated student or group... check that 'git clone' is used in an empty folder."*
   - **Rationale:** Prevents post-deadline tampering or hidden local modifications. Cloning into an empty directory ensures that only commits officially received by `Vogsphere` are evaluated.
2. **Anti-Spoofing & Alias Verification:**
   - *"Check carefully that no malicious aliases were used to fool you and make you evaluate something that is not the content of the official repository."*
   - **Rationale:** Students could alter `~/.bashrc` or `~/.zshrc` to alias commands like `git`, `lsblk`, or `ufw` to pre-recorded mock outputs. Evaluators must audit environment shell configurations before beginning.
3. **Zero-Tolerance Fault Gate:**
   - Any unhandled `SIGSEGV`, memory leak, or undefined behavior immediately halts evaluation with a final grade of **`0`**. Verified cheating results in a punitive grade of **`-42`**.

### B. Cryptographic Disk Signature Verification
- *"Ensure that the 'signature.txt' file is present at the root of the cloned repository. Check that the signature contained in 'signature.txt' is identical to that of the '.vdi' file of the virtual machine to be evaluated. A simple 'diff' should allow you to compare the two signatures."*
- **Engineering Problem:** Virtual disk images (`.vdi`) span gigabytes and cannot be committed directly to Git.
- **Solution:** The student commits a `sha1sum` hash in `signature.txt`. During the evaluation, the peer computes the checksum of the `.vdi` **prior to booting** (as booting mutates disk metadata and invalidates the digest).

### C. Live Mutation Testing
Rather than reviewing static configurations, the student must execute live changes on demand:
1. **User and PAM Policies:**
   - Provision a new user live to validate PAM constraints (`libpam-pwquality` and `/etc/login.defs`), assign them to groups, and explain policy trade-offs.
2. **Hostname & Reboot Persistence:**
   - Change the system hostname live, execute an OS reboot, and verify persistence across `/etc/hostname` and `/etc/hosts`.
3. **UFW Firewall & SSH Port Injection:**
   - Validate port `4242` and root login bans; inject a live rule opening port `8080`, verify its active status table, delete the rule, and authenticate via SSH.
4. **Daemon Monitoring & Cron Mutation:**
   - Mutate `monitoring.sh` cron frequency from 10 minutes to 1 minute to prove real-time kernel telemetry (`/proc`, `df`, `free`, `ss`), then disable the daemon without altering script file contents.

---

## 3. Engineering Pedagogical Core

1. **Headless Infrastructure Mastery:**
   - From `Born2beroot` to `Inception` (bare Docker from scratch) and `webserv` (HTTP/1.1 in C++98), students master networking, firewalls, LVM partitioning, PAM, and `systemd` process supervision.
2. **Strict Code Norms (`Norminette`):**
   - Imposing strict constraints (25 lines per function, 4 parameters, 5 local variables) forces modular decomposition and functional clarity.

---

## 4. Coding & Engineering Standards

### A. C Standards (`Norminette` + Compiler Gates)
- **Compilation Gate:** Built strictly with `cc -Wall -Wextra -Werror`. A single compiler warning causes immediate failure.
- **Structural Norms:**
  - Function length: **Maximum 25 lines** (excluding braces).
  - Line width: **Maximum 80 columns**.
  - Functions per translation unit: **Maximum 5 functions**.
  - Parameters per function: **Maximum 4 parameters**.
  - Local variables: **Maximum 5 per function**, declared at the top of scope without inline initialization (unless constant).
  - Loops: **Exclusively `while`** (strictly bans `for`, `do...while`, `switch`, `case`, `goto`, ternary `?:`, and Variable-Length Arrays `VLA`).
- **Memory & File Descriptor Hygiene:**
  - Every `malloc` must be guarded against NULL. Every allocated heap byte must be freed before termination.
  - Zero tolerance for buffer overflows or leaked file descriptors (`FD Leak`).

### B. POSIX Shell Scripting Standards
- **Portability & Quoting:**
  - Quote all expansions (`"$var"`) to prevent word splitting and globbing.
  - Use `--` flags to separate options from filenames.
  - Read lines using `IFS= read -r line` to preserve whitespace and backslashes.
- **Fail-Safe Cleanup:**
  - Purge temporary resources using `trap 'rm -f "$tmp"' EXIT INT TERM` and verify exit statuses (`$?`).

---

## 5. Pedagogical Design Principles

1. **Minimalist Contract, Zero Hand-Holding:**
   - Subjects define contracts concisely: filenames, allowed functions, prototypes, and exact examples with `cat -e`.
2. **Constraint-Driven Learning:**
   - Minimized allowed function whitelists force students to build core mechanics directly on kernel syscalls.
3. **Spiral Progression:**
   - Skills build cyclically: from single-character I/O (`ft_putchar`) to memory manipulation (`ft_split`), data structures (`btree_apply_by_level`), and multiplexed network servers (`mini_serv`).
4. **The Error is the Teacher:**
   - Feedback is delivered through minimal failure traces (`Diff KO :(`), prompting deep source code analysis.
5. **All-or-Nothing Mastery:**
   - Passing 19 of 20 tests yields **0%**. Bonuses are strictly locked until mandatory sections achieve **100%**.
6. **Defense-by-Mutation:**
   - Evaluations require students to modify behavior live and explain architectural decisions.

---

## 6. Exercise & Project Specification Template

### Component 1: Official Subject (`subject.en.txt`)
Standard 80-column header and precise behavioral contract:

```text
Assignment name  : ft_ring_buffer
Expected files   : ft_ring_buffer.c ft_ring_buffer.h
Allowed functions: malloc, free, write
--------------------------------------------------------------------------------

Write a circular byte buffer module that supports fixed-capacity non-blocking
writes and reads without memory leaks or buffer overruns.

Your header ft_ring_buffer.h must define the following structure and prototypes:

typedef struct s_ring
{
    unsigned char *buf;
    size_t        cap;
    size_t        head;
    size_t        tail;
    size_t        size;
}                 t_ring;

t_ring  *ring_create(size_t capacity);
int     ring_write(t_ring *r, const void *src, size_t len);
ssize_t ring_read(t_ring *r, void *dst, size_t len);
void    ring_destroy(t_ring *r);

Specifications:
- ring_create allocates and initializes a ring buffer of 'capacity' bytes.
  If capacity is 0 or allocation fails, it returns NULL.
- ring_write writes all 'len' bytes from 'src' into 'r' if and only if
  enough free space is available (len <= cap - size), returning 1 on success
  and 0 without modifying the buffer if space is insufficient or inputs are NULL.
- ring_read reads up to 'len' available bytes into 'dst', advancing the tail
  and returning the number of bytes read, or -1 if 'r' or 'dst' is NULL.
- ring_destroy frees all memory associated with 'r' (safe on NULL).

Examples:
$> ./test_ring | cat -e
write 4 bytes: 1$
read 2 bytes: AB (size=2)$
wrap-around write 4 bytes: 1$
read 6 bytes: CDEFGH (size=0)$
```

### Component 2: Metadata & Constraints (`meta.yml`)
Configures compiler and ELF symbol whitelist (`nm -u`):

```yaml
id: ft_ring_buffer
type: c_function
expected_files:
  - ft_ring_buffer.c
  - ft_ring_buffer.h
allowed_functions:
  - malloc
  - free
  - write
compiler_flags:
  - -Wall
  - -Wextra
  - -Werror
  - -ftrapv
norminette: true
```

### Component 3: Test Matrix & Mutation Guards (`tests.yml`)
Comprehensive mutation-killing test vectors:

1. **Nominal Contract:** Baseline read and write execution.
2. **Boundary & Zero Capacity:** 0 capacity, 0-byte reads, exact capacity fills.
3. **Wrap-Around Arithmetic:** Pointer arithmetic wrapping physical array boundaries.
4. **NULL & Invalid Arguments:** NULL pointer passing across all parameters without SIGSEGV.
5. **Redzone Canary & Leak Audit:** Single-byte canary validation and zero heap leaks.
6. **Algorithmic Stress:** 500,000 operations under 0.5s to fail inefficient $O(N)$ copies.

```yaml
mode: c_function
support_code: |
  #include <stdio.h>
  #include <stdlib.h>
  #include <string.h>
  #include "ft_ring_buffer.h"
fixed_tests:
  - name: null_and_zero_capacity_guards
    code: |
      t_ring *r0 = ring_create(0);
      ring_destroy(NULL);
      printf("%d:%d:%zd\n", r0 == NULL, ring_write(NULL, "a", 1), ring_read(NULL, NULL, 1));
    expected: "1:0:-1"

  - name: wrap_around_and_all_or_nothing_write
    code: |
      char out[16];
      t_ring *r = ring_create(6);
      int w1 = ring_write(r, "ABCD", 4);
      ssize_t n1 = ring_read(r, out, 2);
      out[n1] = '\0';
      int w_fail = ring_write(r, "12345", 5); /* Only 4 bytes free -> must reject completely */
      int w2 = ring_write(r, "EFGH", 4);     /* Wraps around physical array */
      printf("%d:%s:%d:%d:", w1, out, w_fail, w2);
      ssize_t n2 = ring_read(r, out, 6);
      out[n2] = '\0';
      printf("%zd:%s:%zu\n", n2, out, r->size);
      ring_destroy(r);
    expected: "1:AB:0:1:6:CDEFGH:0"
```

### Component 4: 1337HUB Peer Evaluation Scale (`scale.yml`)
Standardized defense worksheet:

```markdown
# 1337HUB Peer-Evaluation Scale: [Project Name]

## Introduction & Social Contract
- Remain polite, courteous, respectful and constructive throughout the evaluation process.
- Grade only the work present in the student's official Git repository cloned into an empty directory.
- If any segfault, memory leak, unexpected crash, or missing signature occurs, the evaluation stops immediately (Grade: 0).

## Step 1: Preliminaries & Integrity Check (10 pts) [Yes / No]
- Verify that the evaluated student is present in person.
- Clone the official repository into an empty folder and inspect for any malicious aliases or unauthorized files.
- Run `norminette` and verify clean compilation with `cc -Wall -Wextra -Werror`.

## Step 2: Conceptual Defense — "Explain Before Checking" (20 pts) [Yes / No]
- Ask the student to explain the internal architecture and data structures without running the program first.
- Ask why they chose this specific design and what its trade-offs are.
- ("Answering 'because the subject asks for it' does not count. If the explanation is unclear, evaluation terminates.")

## Step 3: Live Mutation & Persistence Verification (50 pts) [Yes / No]
- Verify dynamic adaptability by requesting live changes:
  1. Inject boundary conditions or modified rules in real time.
  2. Verify output updates and log streaming.
  3. Restore original state and confirm zero heap leaks (`leaks` / `valgrind`).

## Step 4: Bonus Part (25 pts — Slider 0..5)
- Evaluate the bonus section IF AND ONLY IF the mandatory section is completely and flawlessly validated.
```
