/* ************************************************************************** */
/*                                                                            */
/*   dt_diagnostics.h                                                         */
/*   Magrathea Production Exit-Status, Signal & Memory Diagnostic Classifier  */
/*   Strictly distinguishes:                                                  */
/*   - Normal zero exit (0)                                                   */
/*   - Nonzero positive exit (1..255, including 6, 7, 8, 11 without markers)  */
/*   - SIGABRT (-6) vs positive exit code 6 / Double Free KO                  */
/*   - SIGSEGV (-11) vs positive exit code 11                                 */
/*   - SIGBUS (-7) vs positive exit code 7                                    */
/*   - SIGFPE (-8) vs positive exit code 8                                    */
/*   - Timeout                                                                */
/*   - Leak KO (42), Redzone KO (43), Invalid Free / Arena Ownership KO (44), */
/*     Tracking Exhausted KO (45), Double Free KO (46 or 6 + marker)          */
/*   - Compiler failure & Output limit exceeded                               */
/*                                                                            */
/* ************************************************************************** */

#ifndef DT_DIAGNOSTICS_H
#define DT_DIAGNOSTICS_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum e_dt_diag_kind {
    DT_DIAG_OK = 0,
    DT_DIAG_NONZERO_EXIT = 1,
    DT_DIAG_SIGABRT = 2,
    DT_DIAG_SIGSEGV = 3,
    DT_DIAG_SIGBUS = 4,
    DT_DIAG_SIGFPE = 5,
    DT_DIAG_OTHER_SIGNAL = 6,
    DT_DIAG_TIMEOUT = 7,
    DT_DIAG_LEAK_KO = 8,
    DT_DIAG_REDZONE_KO = 9,
    DT_DIAG_INVALID_FREE_KO = 10,
    DT_DIAG_ARENA_OWNERSHIP_KO = 11,
    DT_DIAG_TRACKING_EXHAUSTED_KO = 12,
    DT_DIAG_DOUBLE_FREE_KO = 13,
    DT_DIAG_COMPILE_FAILURE = 14,
    DT_DIAG_OUTPUT_LIMIT = 15
} dt_diag_kind_t;

typedef struct s_dt_diag_result {
    dt_diag_kind_t kind;
    int            is_signal;
    int            signal_number;
    int            exit_code;
    int            is_memory_error;
    char           status_label[96];
    char           reason_detail[160];
} dt_diag_result_t;

int         dt_diag_classify_execution(
                int               signed_returncode,
                int               timed_out,
                int               compile_failed,
                int               output_exceeded,
                const char       *stderr_text,
                dt_diag_result_t *out
            );

int         dt_diag_from_wait_status(
                int               raw_wstatus,
                int               timed_out,
                const char       *stderr_text,
                dt_diag_result_t *out
            );

const char *dt_diag_kind_name(dt_diag_kind_t kind);
bool        dt_diag_is_signal(const dt_diag_result_t *res);
bool        dt_diag_is_memory_violation(const dt_diag_result_t *res);

#ifdef __cplusplus
}
#endif

#endif /* DT_DIAGNOSTICS_H */
