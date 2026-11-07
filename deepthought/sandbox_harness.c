/* ************************************************************************** */
/*                                                                            */
/*   sandbox_harness.c                                                        */
/*   1337 / 42 Deepthought Strict C Sandbox & Memory Leak Auditor (v2.4)      */
/*   Gen-4/Gen-5 Integration:                                                 */
/*   - Uses Magrathea Arena Adapter (dt_arena / tsoding/arena mmap backend)   */
/*     for harness-owned tracking node slabs and harness scratch buffers      */
/*   - Guarantees strict domain separation between Harness Arena memory       */
/*     (mmap anonymous regions) and Student Heap (__wrap_malloc/free)         */
/*   - Detects illegal student free()/realloc() of Harness Arena pointers     */
/*   - Emits real measured Arena & Heap telemetry via DT_ARENA_STATS_FILE     */
/*   - Supports both -Wl,--wrap=malloc student linking and direct Criterion   */
/*     unit-test linking (DT_UNIT_TEST_MODE) with libgcov flush before _exit  */
/* ************************************************************************** */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef DT_ARENA_EXTERNAL_LINK
#  if defined(__has_include)
#    if __has_include("../trusted_harness/dt_arena.c")
#      include "../trusted_harness/dt_arena.c"
#    elif __has_include("dt_arena.c")
#      include "dt_arena.c"
#    else
#      error "Cannot locate trusted_harness/dt_arena.c"
#    endif
#  else
#    include "../trusted_harness/dt_arena.c"
#  endif
#else
#  include "dt_arena.h"
#endif

#if defined(__has_include)
#  if __has_include("../trusted_harness/dt_sandbox_harness.h")
#    include "../trusted_harness/dt_sandbox_harness.h"
#  elif __has_include("dt_sandbox_harness.h")
#    include "dt_sandbox_harness.h"
#  endif
#endif

#ifdef DT_WRAP_MALLOC

#ifdef DT_COVERAGE_INSTRUMENTED
extern void __gcov_dump(void);
static void dt_cov_flush_before_exit(void) { __gcov_dump(); }
#else
static void dt_cov_flush_before_exit(void) {}
#endif

#define DT_LEFT_REDZONE_SIZE  16
#define DT_RIGHT_REDZONE_SIZE 16
#define DT_LEFT_CANARY        0x5A
#define DT_RIGHT_CANARY       0xA5

#define DT_HASH_BUCKETS       16384
#define DT_STATIC_POOL_NODES  64
#define DT_SLAB_NODES         512
#define DT_DEFAULT_MAX_ALLOCS 1048576

typedef struct s_alloc_node {
    void                *user_ptr;
    void                *raw_ptr;
    size_t              size;
    int                 active;
    struct s_alloc_node *next;
} t_alloc_node;

static t_alloc_node *g_buckets[DT_HASH_BUCKETS];
static t_alloc_node g_static_pool[DT_STATIC_POOL_NODES];
static size_t       g_static_used = 0;
static t_alloc_node *g_free_nodes = NULL;
static size_t       g_total_tracked = 0;
static size_t       g_max_allocs = DT_DEFAULT_MAX_ALLOCS;

static dt_arena_t   g_harness_arena;
static int          g_harness_arena_ready = 0;

static int          g_malloc_calls = 0;
static int          g_free_calls = 0;
static int          g_fail_at = -1;
static int          g_chunk_read = -1;
static int          g_check_leaks = -1;
static int          g_in_hook = 0;
static int          g_audit_done = 0;

#ifdef DT_UNIT_TEST_MODE
static void *__real_malloc(size_t size)                  { return (malloc(size)); }
static void *__real_calloc(size_t nmemb, size_t size)    { return (calloc(nmemb, size)); }
static void *__real_realloc(void *ptr, size_t size)      { return (realloc(ptr, size)); }
static char *__real_strdup(const char *s)                { return (strdup(s)); }
static void  __real_free(void *ptr)                      { free(ptr); }
static ssize_t __real_read(int fd, void *buf, size_t c)  { return (read(fd, buf, c)); }
static void  __real_exit(int status) __attribute__((noreturn));
static void  __real__exit(int status) __attribute__((noreturn));
static void  __real__Exit(int status) __attribute__((noreturn));
static void  __real_exit(int status)  { dt_cov_flush_before_exit(); _exit(status); }
static void  __real__exit(int status) { dt_cov_flush_before_exit(); _exit(status); }
static void  __real__Exit(int status) { dt_cov_flush_before_exit(); _Exit(status); }
#else
extern void     *__real_malloc(size_t size);
extern void     *__real_calloc(size_t nmemb, size_t size);
extern void     *__real_realloc(void *ptr, size_t size);
extern char     *__real_strdup(const char *s);
extern void     __real_free(void *ptr);
extern ssize_t  __real_read(int fd, void *buf, size_t count);
extern void     __real_exit(int status) __attribute__((noreturn));
extern void     __real__exit(int status) __attribute__((noreturn));
extern void     __real__Exit(int status) __attribute__((noreturn));
#endif

static void dt_terminate_with_code(int code) __attribute__((noreturn));
static void dt_terminate_with_code(int code)
{
    fflush(stderr);
    dt_cov_flush_before_exit();
    __real__exit(code);
}

static void dt_ensure_harness_arena(void)
{
    if (!g_harness_arena_ready)
    {
        if (dt_arena_init(&g_harness_arena) == 0)
        {
            g_harness_arena_ready = 1;
            t_alloc_node *init_slab = (t_alloc_node *)dt_arena_alloc_aligned(
                &g_harness_arena,
                sizeof(t_alloc_node) * DT_SLAB_NODES,
                _Alignof(t_alloc_node)
            );
            if (init_slab)
            {
                for (size_t i = 0; i < DT_SLAB_NODES; i++)
                {
                    init_slab[i].next = g_free_nodes;
                    g_free_nodes = &init_slab[i];
                }
            }
        }
    }
}

/* Public Harness Arena API for synthesized test drivers (__dt_main.c / __dt_oracle_*.c) */
dt_arena_t *dt_harness_arena(void)
{
    dt_ensure_harness_arena();
    return (&g_harness_arena);
}

void *dt_harness_alloc(size_t size_bytes)
{
    dt_ensure_harness_arena();
    return (dt_arena_alloc_aligned(&g_harness_arena, size_bytes, 16));
}

char *dt_harness_strdup(const char *s)
{
    dt_ensure_harness_arena();
    return (dt_arena_strdup(&g_harness_arena, s));
}

dt_arena_mark_t dt_harness_mark(void)
{
    dt_ensure_harness_arena();
    return (dt_arena_mark(&g_harness_arena));
}

int dt_harness_rewind(dt_arena_mark_t m)
{
    dt_ensure_harness_arena();
    return (dt_arena_rewind(&g_harness_arena, m));
}

void dt_harness_reset_state(void)
{
    for (size_t b = 0; b < DT_HASH_BUCKETS; b++)
    {
        t_alloc_node *cur = g_buckets[b];
        while (cur)
        {
            if (cur->active && cur->raw_ptr)
            {
                __real_free(cur->raw_ptr);
                cur->raw_ptr = NULL;
                cur->active = 0;
            }
            cur = cur->next;
        }
        g_buckets[b] = NULL;
    }
    if (g_harness_arena_ready)
    {
        dt_arena_destroy(&g_harness_arena);
        g_harness_arena_ready = 0;
    }
    g_free_nodes = NULL;
    g_static_used = 0;
    g_total_tracked = 0;
    g_max_allocs = DT_DEFAULT_MAX_ALLOCS;
    g_malloc_calls = 0;
    g_free_calls = 0;
    g_fail_at = -1;
    g_chunk_read = -1;
    g_check_leaks = -1;
    g_in_hook = 0;
    g_audit_done = 0;
}

void dt_harness_get_counters(
    int    *out_malloc_calls,
    int    *out_free_calls,
    size_t *out_active_blocks,
    size_t *out_active_bytes
)
{
    size_t active_blocks = 0;
    size_t active_bytes = 0;
    for (size_t b = 0; b < DT_HASH_BUCKETS; b++)
    {
        for (t_alloc_node *cur = g_buckets[b]; cur != NULL; cur = cur->next)
        {
            if (cur->active)
            {
                active_blocks++;
                active_bytes += cur->size;
            }
        }
    }
    if (out_malloc_calls)
        *out_malloc_calls = g_malloc_calls;
    if (out_free_calls)
        *out_free_calls = g_free_calls;
    if (out_active_blocks)
        *out_active_blocks = active_blocks;
    if (out_active_bytes)
        *out_active_bytes = active_bytes;
}

void dt_harness_set_in_hook(int in_hook)
{
    g_in_hook = in_hook;
}

static size_t dt_hash_ptr(const void *p)
{
    uintptr_t v = (uintptr_t)p;
    v = (v >> 4) ^ (v >> 16);
    return (size_t)(v & (DT_HASH_BUCKETS - 1));
}

static void dt_init_env(void)
{
    dt_ensure_harness_arena();
    if (g_fail_at <= 0)
    {
        const char *env_fail = getenv("DT_FAIL_MALLOC_AT");
        int new_fail = (env_fail && *env_fail) ? atoi(env_fail) : 0;
        if (new_fail > 0)
        {
            g_malloc_calls = 0;
            g_fail_at = new_fail;
        }
        else
            g_fail_at = 0;
    }
    if (g_chunk_read == -1)
    {
        const char *env_chunk = getenv("DT_CHUNK_READ");
        g_chunk_read = (env_chunk && strcmp(env_chunk, "1") == 0) ? 1 : 0;
    }
    if (g_check_leaks == -1)
    {
        const char *env_leaks = getenv("DT_CHECK_LEAKS");
        g_check_leaks = (env_leaks && strcmp(env_leaks, "1") == 0) ? 1 : 0;
        const char *env_max = getenv("DT_MAX_ALLOCS");
        if (env_max && *env_max)
        {
            long mv = atol(env_max);
            if (mv > 0)
                g_max_allocs = (size_t)mv;
        }
    }
}

__attribute__((constructor))
static void dt_constructor_init(void)
{
    dt_ensure_harness_arena();
}

static void dt_emit_arena_telemetry(int leaked_blocks, size_t leaked_bytes)
{
    const char *stats_file = getenv("DT_ARENA_STATS_FILE");
    if (!stats_file || !*stats_file || !g_harness_arena_ready)
        return;
    dt_arena_stats_t st;
    if (dt_arena_get_stats(&g_harness_arena, &st) != 0)
        return;
    char *json_line = dt_arena_sprintf(
        &g_harness_arena,
        "{\"regions_allocated\":%zu,\"active_regions\":%zu,\"reserved_bytes\":%zu,"
        "\"used_bytes\":%zu,\"peak_reserved_bytes\":%zu,\"peak_used_bytes\":%zu,"
        "\"total_allocations\":%zu,\"reused_regions\":%zu,\"allocation_failures\":%zu,"
        "\"reset_count\":%zu,\"rewind_count\":%zu,\"trim_count\":%zu,"
        "\"student_malloc_calls\":%d,\"student_free_calls\":%d,"
        "\"student_leaked_blocks\":%d,\"student_leaked_bytes\":%zu}\n",
        st.regions_allocated,
        st.active_regions,
        st.reserved_bytes,
        st.used_bytes,
        st.peak_reserved_bytes,
        st.peak_used_bytes,
        st.total_allocations,
        st.reused_regions,
        st.allocation_failures,
        st.reset_count,
        st.rewind_count,
        st.trim_count,
        g_malloc_calls,
        g_free_calls,
        leaked_blocks,
        leaked_bytes
    );
    if (!json_line)
        return;
    int fd = open(stats_file, O_WRONLY | O_CREAT | O_APPEND, 0600);
    if (fd >= 0)
    {
        size_t len = strlen(json_line);
        ssize_t unused = write(fd, json_line, len);
        (void)unused;
        close(fd);
    }
}

static void dt_verify_redzone(const t_alloc_node *node)
{
    if (!node || !node->user_ptr || !node->raw_ptr)
        return;
    const unsigned char *left_rz = (const unsigned char *)node->raw_ptr;
    for (size_t k = 0; k < DT_LEFT_REDZONE_SIZE; k++)
    {
        if (left_rz[k] != DT_LEFT_CANARY)
        {
            fprintf(
                stderr,
                "[REDZONE KO]: Heap buffer underflow (write at offset -%zu before malloc(%zu))!\n",
                DT_LEFT_REDZONE_SIZE - k,
                node->size
            );
            dt_emit_arena_telemetry(0, 0);
            dt_terminate_with_code(43);
        }
    }
    const unsigned char *right_rz = (const unsigned char *)node->user_ptr + node->size;
    for (size_t k = 0; k < DT_RIGHT_REDZONE_SIZE; k++)
    {
        if (right_rz[k] != DT_RIGHT_CANARY)
        {
            fprintf(
                stderr,
                "[REDZONE KO]: Heap buffer overflow (off-by-one write at offset +%zu past malloc(%zu))!\n",
                k,
                node->size
            );
            dt_emit_arena_telemetry(0, 0);
            dt_terminate_with_code(43);
        }
    }
}

static t_alloc_node *dt_find_node(const void *user_ptr)
{
    size_t idx = dt_hash_ptr(user_ptr);
    t_alloc_node *cur = g_buckets[idx];
    while (cur)
    {
        if (cur->user_ptr == user_ptr)
            return (cur);
        cur = cur->next;
    }
    return (NULL);
}

static t_alloc_node *dt_acquire_node(void)
{
    if (g_total_tracked >= g_max_allocs)
    {
        fprintf(
            stderr,
            "[TRACKING EXHAUSTED KO]: Allocation count exceeded limit (%zu)!\n",
            g_max_allocs
        );
        dt_emit_arena_telemetry(0, 0);
        dt_terminate_with_code(45);
    }
    if (g_free_nodes)
    {
        t_alloc_node *n = g_free_nodes;
        g_free_nodes = n->next;
        g_total_tracked++;
        return (n);
    }
    /* Allocate tracking slabs from the Harness mmap Arena first */
    dt_ensure_harness_arena();
    t_alloc_node *slab = (t_alloc_node *)dt_arena_alloc_aligned(
        &g_harness_arena,
        sizeof(t_alloc_node) * DT_SLAB_NODES,
        _Alignof(t_alloc_node)
    );
    if (slab)
    {
        for (size_t i = 1; i < DT_SLAB_NODES; i++)
        {
            slab[i].next = g_free_nodes;
            g_free_nodes = &slab[i];
        }
        g_total_tracked++;
        return (&slab[0]);
    }
    /* Emergency static fallback pool if RLIMIT_AS prevents further mmap */
    if (g_static_used < DT_STATIC_POOL_NODES)
    {
        g_total_tracked++;
        return (&g_static_pool[g_static_used++]);
    }
    fprintf(stderr, "[TRACKING EXHAUSTED KO]: Out of memory allocating tracking slab in arena!\n");
    dt_emit_arena_telemetry(0, 0);
    dt_terminate_with_code(45);
}

static void *dt_tracked_alloc(size_t size, int zero_fill)
{
    dt_init_env();
    g_malloc_calls++;
    if (g_fail_at > 0 && g_malloc_calls == g_fail_at)
        return (NULL);
    if (size > SIZE_MAX - (DT_LEFT_REDZONE_SIZE + DT_RIGHT_REDZONE_SIZE))
    {
        errno = ENOMEM;
        return (NULL);
    }
    size_t total_raw = DT_LEFT_REDZONE_SIZE + size + DT_RIGHT_REDZONE_SIZE;
    void *raw = __real_malloc(total_raw);
    if (!raw)
        return (NULL);
    unsigned char *user = (unsigned char *)raw + DT_LEFT_REDZONE_SIZE;
    memset(raw, DT_LEFT_CANARY, DT_LEFT_REDZONE_SIZE);
    if (zero_fill && size > 0)
        memset(user, 0, size);
    memset(user + size, DT_RIGHT_CANARY, DT_RIGHT_REDZONE_SIZE);

    t_alloc_node *existing = dt_find_node(user);
    if (existing)
    {
        existing->raw_ptr = raw;
        existing->size = size;
        existing->active = 1;
    }
    else
    {
        t_alloc_node *node = dt_acquire_node();
        size_t idx = dt_hash_ptr(user);
        node->user_ptr = user;
        node->raw_ptr = raw;
        node->size = size;
        node->active = 1;
        node->next = g_buckets[idx];
        g_buckets[idx] = node;
    }
    return (user);
}

void *__wrap_malloc(size_t size)
{
    if (g_in_hook)
        return (__real_malloc(size));
    g_in_hook = 1;
    void *res = dt_tracked_alloc(size, 0);
    g_in_hook = 0;
    return (res);
}

void *__wrap_calloc(size_t nmemb, size_t size)
{
    if (g_in_hook)
        return (__real_calloc(nmemb, size));
    g_in_hook = 1;
    if (size != 0 && nmemb > SIZE_MAX / size)
    {
        errno = ENOMEM;
        g_in_hook = 0;
        return (NULL);
    }
    void *res = dt_tracked_alloc(nmemb * size, 1);
    g_in_hook = 0;
    return (res);
}

void __wrap_free(void *ptr)
{
    dt_init_env();
    if (!ptr)
        return;
    if (g_in_hook)
    {
        __real_free(ptr);
        return;
    }
    g_in_hook = 1;
    if (g_harness_arena_ready && dt_arena_owns_ptr(&g_harness_arena, ptr))
    {
        fprintf(
            stderr,
            "[ARENA OWNERSHIP KO]: Student attempted to free harness arena pointer %p!\n",
            ptr
        );
        dt_emit_arena_telemetry(0, 0);
        dt_terminate_with_code(44);
    }
    t_alloc_node *node = dt_find_node(ptr);
    if (!node)
    {
        fprintf(stderr, "[INVALID FREE KO]: Attempted to free untracked or misaligned pointer %p!\n", ptr);
        dt_emit_arena_telemetry(0, 0);
        dt_terminate_with_code(44);
    }
    if (!node->active)
    {
        fprintf(stderr, "[DOUBLE FREE KO]: Attempted to free already-freed pointer %p!\n", ptr);
        dt_emit_arena_telemetry(0, 0);
        dt_terminate_with_code(6);
    }
    dt_verify_redzone(node);
    node->active = 0;
    g_free_calls++;
    void *raw_to_free = node->raw_ptr;
    node->raw_ptr = NULL;
    g_in_hook = 0;
    __real_free(raw_to_free);
}

void *__wrap_realloc(void *ptr, size_t size)
{
    if (g_in_hook)
        return (__real_realloc(ptr, size));
    if (!ptr)
        return (__wrap_malloc(size));
    if (size == 0)
    {
        __wrap_free(ptr);
        return (NULL);
    }
    g_in_hook = 1;
    if (g_harness_arena_ready && dt_arena_owns_ptr(&g_harness_arena, ptr))
    {
        fprintf(
            stderr,
            "[ARENA OWNERSHIP KO]: Student attempted to realloc harness arena pointer %p!\n",
            ptr
        );
        dt_emit_arena_telemetry(0, 0);
        dt_terminate_with_code(44);
    }
    t_alloc_node *old_node = dt_find_node(ptr);
    if (!old_node || !old_node->active)
    {
        fprintf(stderr, "[INVALID FREE KO]: Attempted to realloc untracked or freed pointer %p!\n", ptr);
        dt_emit_arena_telemetry(0, 0);
        dt_terminate_with_code(44);
    }
    dt_verify_redzone(old_node);
    size_t old_size = old_node->size;
    void *new_user = dt_tracked_alloc(size, 0);
    if (!new_user)
    {
        g_in_hook = 0;
        return (NULL);
    }
    size_t copy_len = (old_size < size) ? old_size : size;
    if (copy_len > 0)
        memcpy(new_user, ptr, copy_len);
    old_node->active = 0;
    g_free_calls++;
    void *old_raw = old_node->raw_ptr;
    old_node->raw_ptr = NULL;
    __real_free(old_raw);
    g_in_hook = 0;
    return (new_user);
}

char *__wrap_strdup(const char *s)
{
    if (g_in_hook)
        return (__real_strdup(s));
    if (!s)
        return (NULL);
    size_t len = strlen(s);
    char *copy = (char *)__wrap_malloc(len + 1);
    if (!copy)
        return (NULL);
    memcpy(copy, s, len + 1);
    return (copy);
}

ssize_t __wrap_read(int fd, void *buf, size_t count)
{
    dt_init_env();
    if (g_chunk_read && count > 1)
        count = 1;
    return (__real_read(fd, buf, count));
}

size_t dt_get_alloc_size(void *ptr)
{
    t_alloc_node *node = dt_find_node(ptr);
    if (node && node->active)
        return (node->size);
    return (0);
}

static void dt_audit_memory_leaks(void)
{
    if (g_audit_done)
        return;
    g_audit_done = 1;
    dt_init_env();
    const char *env_leaks_now = getenv("DT_CHECK_LEAKS");
    if (env_leaks_now && strcmp(env_leaks_now, "1") == 0)
        g_check_leaks = 1;
    int     leaked_blocks = 0;
    size_t  leaked_bytes = 0;
    for (size_t b = 0; b < DT_HASH_BUCKETS; b++)
    {
        t_alloc_node *cur = g_buckets[b];
        while (cur)
        {
            if (cur->active)
            {
                dt_verify_redzone(cur);
                leaked_blocks++;
                leaked_bytes += cur->size;
            }
            cur = cur->next;
        }
    }
    dt_emit_arena_telemetry(leaked_blocks, leaked_bytes);
    if (g_harness_arena_ready)
    {
        dt_arena_destroy(&g_harness_arena);
        g_harness_arena_ready = 0;
    }
    if (g_check_leaks && leaked_blocks > 0)
    {
        fprintf(
            stderr,
            "[LEAK KO]: Memory leak detected: %d unfreed block(s) (%zu bytes total)!\n",
            leaked_blocks,
            leaked_bytes
        );
        dt_terminate_with_code(42);
    }
}

void dt_harness_audit_leaks_now(void)
{
    dt_audit_memory_leaks();
}

void __wrap_exit(int status)
{
    if (status == 0)
        dt_audit_memory_leaks();
    __real_exit(status);
}

void __wrap__exit(int status)
{
    if (status == 0)
        dt_audit_memory_leaks();
    __real__exit(status);
}

void __wrap__Exit(int status)
{
    if (status == 0)
        dt_audit_memory_leaks();
    __real__Exit(status);
}

#ifndef DT_UNIT_TEST_MODE
__attribute__((destructor))
static void dt_destructor_audit(void)
{
    dt_audit_memory_leaks();
}
#endif

#endif
