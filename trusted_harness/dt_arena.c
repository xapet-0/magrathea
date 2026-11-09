/* ************************************************************************** */
/*                                                                            */
/*   dt_arena.c                                                               */
/*   Magrathea Gen-4/Gen-5 (ARENA-01) — Safe Adapter Implementation           */
/*   Wraps unmodified third_party/tsoding_arena/arena.h with:                 */
/*   - ARENA_BACKEND_LINUX_MMAP (zero collision with --wrap=malloc)           */
/*   - Arithmetic overflow guards before new_region() / arena_alloc()         */
/*   - Non-aborting OOM trap on ARENA_ASSERT(r != MAP_FAILED) via setjmp      */
/*   - Power-of-two alignment up to 64+ bytes (max_align_t / SIMD safe)       */
/*   - Epoch-validated marks & null-safe arena_trim()                         */
/*   - Live region traversal telemetry                                        */
/*                                                                            */
/* ************************************************************************** */

#define _GNU_SOURCE
#include <errno.h>
#include <limits.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef DT_COVERAGE_INSTRUMENTED
extern void __gcov_dump(void);
static void dt_arena_cov_flush(void) { __gcov_dump(); }
#else
static void dt_arena_cov_flush(void) {}
#endif

static __thread jmp_buf g_dt_arena_oom_jmp;
static __thread int     g_dt_arena_oom_trap_active = 0;
static __thread int     g_dt_arena_oom_inject_countdown = 0;

void dt_arena_inject_oom_after(int calls_until_fail)
{
    g_dt_arena_oom_inject_countdown = calls_until_fail;
}

static void dt_arena_assert_handler(const char *expr, const char *file, int line)
{
    if (g_dt_arena_oom_trap_active)
    {
        errno = ENOMEM;
        longjmp(g_dt_arena_oom_jmp, 1);
    }
    fprintf(stderr, "[DT_ARENA FATAL]: Upstream assertion failed: %s (%s:%d)\n", expr, file, line);
    fflush(stderr);
    dt_arena_cov_flush();
    abort();
}

#define ARENA_ASSERT(cond)                                                     \
    do {                                                                       \
        if (!(cond))                                                           \
            dt_arena_assert_handler(#cond, __FILE__, __LINE__);                \
    } while (0)

#define ARENA_BACKEND ARENA_BACKEND_LINUX_MMAP
#define ARENA_IMPLEMENTATION
#include "dt_arena.h"

/* Maximum safe byte request that cannot overflow:
 *   1) (size_bytes + sizeof(uintptr_t) - 1) / sizeof(uintptr_t)
 *   2) sizeof(Region) + sizeof(uintptr_t) * capacity
 */
#define DT_ARENA_MAX_BYTES ((SIZE_MAX - sizeof(Region) - sizeof(uintptr_t)) & ~(sizeof(uintptr_t) - 1))

/* Noinline setjmp trampolines so GCC -O2 -Werror=clobbered is 100% clean */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wclobbered"
__attribute__((noinline))
static void *dt_trampoline_alloc(Arena *raw, size_t effective_bytes)
{
    g_dt_arena_oom_trap_active = 1;
    if (setjmp(g_dt_arena_oom_jmp) == 0)
    {
        if (g_dt_arena_oom_inject_countdown > 0 && --g_dt_arena_oom_inject_countdown == 0)
            dt_arena_assert_handler("r != MAP_FAILED (injected OOM)", __FILE__, __LINE__);
        void *res = arena_alloc(raw, effective_bytes);
        g_dt_arena_oom_trap_active = 0;
        return (res);
    }
    g_dt_arena_oom_trap_active = 0;
    return (NULL);
}

__attribute__((noinline))
static void *dt_trampoline_realloc(Arena *raw, void *oldptr, size_t oldsz, size_t newsz)
{
    g_dt_arena_oom_trap_active = 1;
    if (setjmp(g_dt_arena_oom_jmp) == 0)
    {
        if (g_dt_arena_oom_inject_countdown > 0 && --g_dt_arena_oom_inject_countdown == 0)
            dt_arena_assert_handler("r != MAP_FAILED (injected OOM)", __FILE__, __LINE__);
        void *res = arena_realloc(raw, oldptr, oldsz, newsz);
        g_dt_arena_oom_trap_active = 0;
        return (res);
    }
    g_dt_arena_oom_trap_active = 0;
    return (NULL);
}

__attribute__((noinline))
static char *dt_trampoline_strdup(Arena *raw, const char *cstr)
{
    g_dt_arena_oom_trap_active = 1;
    if (setjmp(g_dt_arena_oom_jmp) == 0)
    {
        if (g_dt_arena_oom_inject_countdown > 0 && --g_dt_arena_oom_inject_countdown == 0)
            dt_arena_assert_handler("r != MAP_FAILED (injected OOM)", __FILE__, __LINE__);
        char *res = arena_strdup(raw, cstr);
        g_dt_arena_oom_trap_active = 0;
        return (res);
    }
    g_dt_arena_oom_trap_active = 0;
    return (NULL);
}

__attribute__((noinline))
static void *dt_trampoline_memdup(Arena *raw, const void *data, size_t size)
{
    g_dt_arena_oom_trap_active = 1;
    if (setjmp(g_dt_arena_oom_jmp) == 0)
    {
        if (g_dt_arena_oom_inject_countdown > 0 && --g_dt_arena_oom_inject_countdown == 0)
            dt_arena_assert_handler("r != MAP_FAILED (injected OOM)", __FILE__, __LINE__);
        void *res = arena_memdup(raw, (void *)data, size);
        g_dt_arena_oom_trap_active = 0;
        return (res);
    }
    g_dt_arena_oom_trap_active = 0;
    return (NULL);
}

__attribute__((noinline))
static char *dt_trampoline_vsprintf(Arena *raw, const char *format, va_list args)
{
    g_dt_arena_oom_trap_active = 1;
    if (setjmp(g_dt_arena_oom_jmp) == 0)
    {
        if (g_dt_arena_oom_inject_countdown > 0 && --g_dt_arena_oom_inject_countdown == 0)
            dt_arena_assert_handler("r != MAP_FAILED (injected OOM)", __FILE__, __LINE__);
        char *res = arena_vsprintf(raw, format, args);
        g_dt_arena_oom_trap_active = 0;
        return (res);
    }
    g_dt_arena_oom_trap_active = 0;
    return (NULL);
}
#pragma GCC diagnostic pop

static size_t dt_arena_count_regions(const Arena *raw, size_t *out_reserved, size_t *out_used)
{
    size_t count = 0;
    size_t reserved = 0;
    size_t used = 0;
    for (const Region *r = (raw != NULL) ? raw->begin : NULL; r != NULL; r = r->next)
    {
        count++;
        reserved += sizeof(Region) + (r->capacity * sizeof(uintptr_t));
        used += r->count * sizeof(uintptr_t);
    }
    if (out_reserved)
        *out_reserved = reserved;
    if (out_used)
        *out_used = used;
    return (count);
}

static void dt_arena_refresh_stats(dt_arena_t *a, size_t prev_active_regions, const Region *prev_end)
{
    size_t reserved = 0;
    size_t used = 0;
    size_t active = dt_arena_count_regions(&a->raw, &reserved, &used);
    if (active > prev_active_regions)
        a->stats.regions_allocated += (active - prev_active_regions);
    else if (prev_end != NULL && a->raw.end != prev_end && active == prev_active_regions)
        a->stats.reused_regions++;
    a->stats.active_regions = active;
    a->stats.reserved_bytes = reserved;
    a->stats.used_bytes = used;
    if (reserved > a->stats.peak_reserved_bytes)
        a->stats.peak_reserved_bytes = reserved;
    if (used > a->stats.peak_used_bytes)
        a->stats.peak_used_bytes = used;
}

static bool dt_arena_valid(const dt_arena_t *a)
{
    return (a != NULL && a->magic == DT_ARENA_MAGIC);
}

int dt_arena_init(dt_arena_t *a)
{
    if (!a)
    {
        errno = EINVAL;
        return (-1);
    }
    memset(a, 0, sizeof(*a));
    a->raw.begin = NULL;
    a->raw.end = NULL;
    a->epoch = 1;
    a->magic = DT_ARENA_MAGIC;
    return (0);
}

void dt_arena_destroy(dt_arena_t *a)
{
    if (!dt_arena_valid(a))
        return;
    arena_free(&a->raw);
    a->epoch++;
    a->stats.active_regions = 0;
    a->stats.reserved_bytes = 0;
    a->stats.used_bytes = 0;
    a->magic = 0;
}

void *dt_arena_alloc(dt_arena_t *a, size_t size_bytes)
{
    if (!dt_arena_valid(a))
    {
        errno = EINVAL;
        return (NULL);
    }
    size_t effective_bytes = (size_bytes == 0) ? sizeof(uintptr_t) : size_bytes;
    if (effective_bytes > DT_ARENA_MAX_BYTES)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    const Region *prev_end = a->raw.end;
    size_t prev_count = prev_end ? prev_end->count : 0;
    size_t prev_active = a->stats.active_regions;

    void *ptr = dt_trampoline_alloc(&a->raw, effective_bytes);
    if (!ptr)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    a->stats.total_allocations++;
    if (prev_end != NULL && a->raw.end == prev_end)
    {
        size_t delta_bytes = (a->raw.end->count - prev_count) * sizeof(uintptr_t);
        a->stats.used_bytes += delta_bytes;
        if (a->stats.used_bytes > a->stats.peak_used_bytes)
            a->stats.peak_used_bytes = a->stats.used_bytes;
    }
    else
        dt_arena_refresh_stats(a, prev_active, prev_end);
    return (ptr);
}

void *dt_arena_calloc(dt_arena_t *a, size_t nmemb, size_t size)
{
    if (!dt_arena_valid(a))
    {
        errno = EINVAL;
        return (NULL);
    }
    if (size != 0 && nmemb > SIZE_MAX / size)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    size_t total = nmemb * size;
    void *ptr = dt_arena_alloc(a, total);
    if (ptr && total > 0)
        memset(ptr, 0, total);
    return (ptr);
}

void *dt_arena_alloc_aligned(dt_arena_t *a, size_t size_bytes, size_t alignment)
{
    if (!dt_arena_valid(a))
    {
        errno = EINVAL;
        return (NULL);
    }
    if (alignment == 0 || (alignment & (alignment - 1)) != 0)
    {
        a->stats.allocation_failures++;
        errno = EINVAL;
        return (NULL);
    }
    if (alignment <= sizeof(uintptr_t))
        return (dt_arena_alloc(a, size_bytes));

    size_t effective_bytes = (size_bytes == 0) ? 1 : size_bytes;
    size_t pad_overhead = alignment - sizeof(uintptr_t);
    if (effective_bytes > DT_ARENA_MAX_BYTES - pad_overhead)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    void *raw_ptr = dt_arena_alloc(a, effective_bytes + pad_overhead);
    if (!raw_ptr)
        return (NULL);
    uintptr_t raw_addr = (uintptr_t)raw_ptr;
    uintptr_t mask = (uintptr_t)(alignment - 1);
    uintptr_t aligned_addr = (raw_addr + mask) & ~mask;
    return ((void *)aligned_addr);
}

void *dt_arena_realloc(dt_arena_t *a, void *oldptr, size_t oldsz, size_t newsz)
{
    if (!dt_arena_valid(a))
    {
        errno = EINVAL;
        return (NULL);
    }
    if (oldptr == NULL)
        return (dt_arena_alloc(a, newsz));
    if (newsz <= oldsz)
        return (oldptr);
    if (newsz > DT_ARENA_MAX_BYTES)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    size_t prev_active = dt_arena_count_regions(&a->raw, NULL, NULL);
    const Region *prev_end = a->raw.end;

    void *ptr = dt_trampoline_realloc(&a->raw, oldptr, oldsz, newsz);
    if (!ptr)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    a->stats.total_allocations++;
    dt_arena_refresh_stats(a, prev_active, prev_end);
    return (ptr);
}

char *dt_arena_strdup(dt_arena_t *a, const char *cstr)
{
    if (!dt_arena_valid(a) || !cstr)
    {
        if (dt_arena_valid(a))
            a->stats.allocation_failures++;
        errno = EINVAL;
        return (NULL);
    }
    size_t prev_active = dt_arena_count_regions(&a->raw, NULL, NULL);
    const Region *prev_end = a->raw.end;

    char *dup = dt_trampoline_strdup(&a->raw, cstr);
    if (!dup)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    a->stats.total_allocations++;
    dt_arena_refresh_stats(a, prev_active, prev_end);
    return (dup);
}

void *dt_arena_memdup(dt_arena_t *a, const void *data, size_t size)
{
    if (!dt_arena_valid(a) || (!data && size > 0))
    {
        if (dt_arena_valid(a))
            a->stats.allocation_failures++;
        errno = EINVAL;
        return (NULL);
    }
    if (size == 0)
        return (dt_arena_alloc(a, 0));
    if (size > DT_ARENA_MAX_BYTES)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    size_t prev_active = dt_arena_count_regions(&a->raw, NULL, NULL);
    const Region *prev_end = a->raw.end;

    void *dup = dt_trampoline_memdup(&a->raw, data, size);
    if (!dup)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    a->stats.total_allocations++;
    dt_arena_refresh_stats(a, prev_active, prev_end);
    return (dup);
}

char *dt_arena_vsprintf(dt_arena_t *a, const char *format, va_list args)
{
    if (!dt_arena_valid(a) || !format)
    {
        if (dt_arena_valid(a))
            a->stats.allocation_failures++;
        errno = EINVAL;
        return (NULL);
    }
    size_t prev_active = dt_arena_count_regions(&a->raw, NULL, NULL);
    const Region *prev_end = a->raw.end;

    char *res = dt_trampoline_vsprintf(&a->raw, format, args);
    if (!res)
    {
        a->stats.allocation_failures++;
        errno = ENOMEM;
        return (NULL);
    }
    a->stats.total_allocations++;
    dt_arena_refresh_stats(a, prev_active, prev_end);
    return (res);
}

char *dt_arena_sprintf(dt_arena_t *a, const char *format, ...)
{
    if (!dt_arena_valid(a) || !format)
    {
        if (dt_arena_valid(a))
            a->stats.allocation_failures++;
        errno = EINVAL;
        return (NULL);
    }
    va_list args;
    va_start(args, format);
    char *res = dt_arena_vsprintf(a, format, args);
    va_end(args);
    return (res);
}

dt_arena_mark_t dt_arena_mark(const dt_arena_t *a)
{
    dt_arena_mark_t m;
    memset(&m, 0, sizeof(m));
    if (!dt_arena_valid(a))
        return (m);
    Arena *mutable_raw = (Arena *)&a->raw;
    m.raw = arena_snapshot(mutable_raw);
    m.arena = a;
    m.epoch = a->epoch;
    return (m);
}

/**
 * dt_arena_rewind() - Rewind arena state to a previously captured mark.
 * @a: Target Magrathea arena instance.
 * @m: Snapshot mark obtained via dt_arena_mark().
 *
 * Validates arena magic, epoch, and monotonic backward position so stale marks
 * located ahead of the current allocation cursor are strictly rejected.
 *
 * Context: Process context; mutates arena region counters.
 * Return: 0 on success, or -1 with errno=EINVAL on invalid/future mark.
 */
int dt_arena_rewind(dt_arena_t *a, dt_arena_mark_t m)
{
    if (!dt_arena_valid(a) || m.arena != a || m.epoch != a->epoch)
    {
        errno = EINVAL;
        return (-1);
    }
    if (m.raw.region != NULL)
    {
        if (a->raw.end == NULL)
        {
            errno = EINVAL;
            return (-1);
        }
        bool found_up_to_end = false;
        for (Region *r = a->raw.begin; r != NULL; r = r->next)
        {
            if (r == m.raw.region)
            {
                found_up_to_end = true;
                break;
            }
            if (r == a->raw.end)
                break;
        }
        if (!found_up_to_end || m.raw.count > m.raw.region->capacity ||
            (m.raw.region == a->raw.end && m.raw.count > a->raw.end->count))
        {
            errno = EINVAL;
            return (-1);
        }
    }
    arena_rewind(&a->raw, m.raw);
    a->stats.rewind_count++;
    dt_arena_refresh_stats(a, a->stats.active_regions, a->raw.end);
    return (0);
}

void dt_arena_reset(dt_arena_t *a)
{
    if (!dt_arena_valid(a))
        return;
    arena_reset(&a->raw);
    a->epoch++;
    a->stats.reset_count++;
    dt_arena_refresh_stats(a, a->stats.active_regions, a->raw.end);
}

int dt_arena_trim(dt_arena_t *a)
{
    if (!dt_arena_valid(a))
    {
        errno = EINVAL;
        return (-1);
    }
    if (a->raw.end != NULL && a->raw.end->next != NULL)
    {
        arena_trim(&a->raw);
        a->epoch++;
    }
    a->stats.trim_count++;
    dt_arena_refresh_stats(a, a->stats.active_regions, a->raw.end);
    return (0);
}

int dt_arena_get_stats(dt_arena_t *a, dt_arena_stats_t *out_stats)
{
    if (!dt_arena_valid(a) || !out_stats)
    {
        errno = EINVAL;
        return (-1);
    }
    dt_arena_refresh_stats(a, a->stats.active_regions, a->raw.end);
    *out_stats = a->stats;
    return (0);
}

bool dt_arena_owns_ptr(const dt_arena_t *a, const void *ptr)
{
    if (!dt_arena_valid(a) || !ptr)
        return (false);
    uintptr_t addr = (uintptr_t)ptr;
    for (const Region *r = a->raw.begin; r != NULL; r = r->next)
    {
        uintptr_t start = (uintptr_t)&r->data[0];
        uintptr_t end = (uintptr_t)&r->data[r->capacity];
        if (addr >= start && addr < end)
            return (true);
    }
    return (false);
}
