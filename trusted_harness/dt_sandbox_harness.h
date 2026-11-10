/* ************************************************************************** */
/*                                                                            */
/*   dt_sandbox_harness.h                                                     */
/*   Public C Interface for deepthought/sandbox_harness.c                     */
/*   Exposes student heap wrappers, redzone checks, leak auditor, and         */
/*   Harness Arena ownership boundaries for production & Criterion tests.     */
/*                                                                            */
/* ************************************************************************** */

#ifndef DT_SANDBOX_HARNESS_H
#define DT_SANDBOX_HARNESS_H

#include "dt_arena.h"
#include <stddef.h>
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

#define DT_EXIT_LEAK_KO               42
#define DT_EXIT_REDZONE_KO            43
#define DT_EXIT_INVALID_FREE_KO       44
#define DT_EXIT_TRACKING_EXHAUSTED_KO 45
#define DT_EXIT_DOUBLE_FREE_KO        6

/* Linker-wrapped student heap and process entry points */
void    *__wrap_malloc(size_t size);
void    *__wrap_calloc(size_t nmemb, size_t size);
void    *__wrap_realloc(void *ptr, size_t size);
char    *__wrap_strdup(const char *s);
void     __wrap_free(void *ptr);
ssize_t  __wrap_read(int fd, void *buf, size_t count);
void     __wrap_exit(int status) __attribute__((noreturn));
void     __wrap__exit(int status) __attribute__((noreturn));
void     __wrap__Exit(int status) __attribute__((noreturn));

/* Allocation size & Harness Arena domain API */
size_t          dt_get_alloc_size(void *ptr);
dt_arena_t     *dt_harness_arena(void);
void           *dt_harness_alloc(size_t size_bytes);
char           *dt_harness_strdup(const char *s);
dt_arena_mark_t dt_harness_mark(void);
int             dt_harness_rewind(dt_arena_mark_t m);

/* State inspection & deterministic test control */
void            dt_harness_reset_state(void);
void            dt_harness_get_counters(
                    int    *out_malloc_calls,
                    int    *out_free_calls,
                    size_t *out_active_blocks,
                    size_t *out_active_bytes
                );
void            dt_harness_set_in_hook(int in_hook);
void            dt_harness_audit_leaks_now(void);

#ifdef __cplusplus
}
#endif

#endif /* DT_SANDBOX_HARNESS_H */
