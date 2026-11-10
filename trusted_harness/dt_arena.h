/* ************************************************************************** */
/*                                                                            */
/*   dt_arena.h                                                               */
/*   Magrathea Gen-4/Gen-5 (ARENA-01) — Safe Adapter for tsoding/arena        */
/*   Uses ARENA_BACKEND_LINUX_MMAP for strict separation from student heap    */
/*                                                                            */
/* ************************************************************************** */

#ifndef DT_ARENA_H
#define DT_ARENA_H

#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Use Linux anonymous mmap backend so harness allocations never touch libc malloc/free */
#ifndef ARENA_BACKEND
#define ARENA_BACKEND 1 /* ARENA_BACKEND_LINUX_MMAP */
#endif

#if defined(__has_include)
#  if __has_include("../third_party/tsoding_arena/arena.h")
#    include "../third_party/tsoding_arena/arena.h"
#  elif __has_include("arena.h")
#    include "arena.h"
#  else
#    error "Cannot locate upstream tsoding/arena header (arena.h)"
#  endif
#else
#  include "../third_party/tsoding_arena/arena.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Forward declarations omitted in upstream arena.h header section (UPSTREAM-BUG-05)
 * required when expanding arena_da_append_many / arena_sb_append_cstr outside
 * the ARENA_IMPLEMENTATION translation unit. */
size_t arena_strlen(const char *s);
void  *arena_memcpy(void *dest, const void *src, size_t n);

typedef struct s_dt_arena_stats {
    size_t   regions_allocated;     /* Cumulative Region allocations via mmap */
    size_t   active_regions;        /* Currently mapped Region nodes in chain */
    size_t   reserved_bytes;        /* Currently mapped bytes (headers + data) */
    size_t   used_bytes;            /* Currently used payload bytes across regions */
    size_t   peak_reserved_bytes;   /* High-water mark of reserved_bytes */
    size_t   peak_used_bytes;       /* High-water mark of used_bytes */
    size_t   total_allocations;     /* Successful allocation requests */
    size_t   reused_regions;        /* Region transitions satisfied without new mmap */
    size_t   allocation_failures;   /* Overflow, invalid alignment, or mmap OOM count */
    size_t   reset_count;           /* Number of dt_arena_reset() calls */
    size_t   rewind_count;          /* Number of successful dt_arena_rewind() calls */
    size_t   trim_count;            /* Number of dt_arena_trim() calls */
} dt_arena_stats_t;

typedef struct s_dt_arena {
    Arena            raw;           /* Underlying upstream tsoding/arena instance */
    uint64_t         epoch;         /* Incremented on init/reset/destroy to catch stale marks */
    uint32_t         magic;         /* Integrity tag (0x4D414752 = 'MAGR') */
    dt_arena_stats_t stats;         /* Live measured runtime telemetry */
} dt_arena_t;

typedef struct s_dt_arena_mark {
    Arena_Mark       raw;           /* Upstream snapshot {Region *region, size_t count} */
    const dt_arena_t *arena;        /* Owning adapter pointer */
    uint64_t         epoch;         /* Arena epoch when mark was captured */
} dt_arena_mark_t;

#define DT_ARENA_MAGIC 0x4D414752U

/* Lifecycle */
int              dt_arena_init(dt_arena_t *a);
void             dt_arena_destroy(dt_arena_t *a);

/* Safe Allocation API */
void            *dt_arena_alloc(dt_arena_t *a, size_t size_bytes);
void            *dt_arena_calloc(dt_arena_t *a, size_t nmemb, size_t size);
void            *dt_arena_alloc_aligned(dt_arena_t *a, size_t size_bytes, size_t alignment);
void            *dt_arena_realloc(dt_arena_t *a, void *oldptr, size_t oldsz, size_t newsz);
char            *dt_arena_strdup(dt_arena_t *a, const char *cstr);
void            *dt_arena_memdup(dt_arena_t *a, const void *data, size_t size);
char            *dt_arena_vsprintf(dt_arena_t *a, const char *format, va_list args);
char            *dt_arena_sprintf(dt_arena_t *a, const char *format, ...)
                     __attribute__((format(printf, 2, 3)));

/* Bulk Lifetime Control */
dt_arena_mark_t  dt_arena_mark(const dt_arena_t *a);
int              dt_arena_rewind(dt_arena_t *a, dt_arena_mark_t m);
void             dt_arena_reset(dt_arena_t *a);
int              dt_arena_trim(dt_arena_t *a);

/* Telemetry, Fault Injection & Inspection */
int              dt_arena_get_stats(dt_arena_t *a, dt_arena_stats_t *out_stats);
bool             dt_arena_owns_ptr(const dt_arena_t *a, const void *ptr);
void             dt_arena_inject_oom_after(int calls_until_fail);

#ifdef __cplusplus
}
#endif

#endif /* DT_ARENA_H */
