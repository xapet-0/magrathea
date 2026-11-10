/* ************************************************************************** */
/*                                                                            */
/*   dt_harness_util.h                                                        */
/*   Magrathea Production Test Harness Utilities                              */
/*   - cat -e formatting ($ at EOL, ^I for tabs)                              */
/*   - Bounded stream truncation (64 KB cap)                                  */
/*   - Return-value and output comparisons with line/col diff locator         */
/*   - Failure aggregation & suite status computation                         */
/*   - Temporary directory creation (0700) & recursive cleanup                */
/*   - Process-group isolated command execution with output capture & timeout */
/*   - JSON result serialization                                              */
/*                                                                            */
/* ************************************************************************** */

#ifndef DT_HARNESS_UTIL_H
#define DT_HARNESS_UTIL_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct s_dt_comparison_result {
    int    matched;
    int    rc_mismatch;
    int    output_mismatch;
    size_t diff_line;
    size_t diff_col;
} dt_comparison_result_t;

typedef struct s_dt_case_status {
    const char *case_name;
    int         passed;
    int         returncode;
    int         timed_out;
    double      duration_ms;
} dt_case_status_t;

typedef struct s_dt_suite_summary {
    size_t total_cases;
    size_t passed_cases;
    size_t failed_cases;
    size_t timeout_cases;
    int    all_passed;
    double total_duration_ms;
} dt_suite_summary_t;

typedef struct s_dt_proc_capture {
    int    signed_returncode;
    int    timed_out;
    size_t stdout_len;
    size_t stderr_len;
    char   stdout_buf[4096];
    char   stderr_buf[4096];
} dt_proc_capture_t;

int dt_format_cat_e(const char *src, size_t src_len, char *dst, size_t dst_cap);
int dt_truncate_output(
        const char *src,
        size_t      src_len,
        size_t      max_bytes,
        char       *dst,
        size_t      dst_cap,
        bool       *out_truncated
    );
int dt_compare_return_and_output(
        int                     expected_rc,
        int                     actual_rc,
        const char             *expected_out,
        const char             *actual_out,
        dt_comparison_result_t *out
    );
int dt_aggregate_case_results(
        const dt_case_status_t *cases,
        size_t                  count,
        dt_suite_summary_t     *out_summary
    );
int dt_create_isolated_tempdir(
        const char *base_dir,
        const char *prefix,
        char       *out_path,
        size_t      out_cap
    );
int dt_cleanup_tempdir(const char *dir_path);
int dt_capture_subprocess(
        char *const        argv[],
        const char        *stdin_data,
        int                timeout_ms,
        dt_proc_capture_t *out_cap
    );
int dt_serialize_harness_report_json(
        const dt_suite_summary_t *summary,
        char                     *out_json,
        size_t                    json_cap
    );

#ifdef __cplusplus
}
#endif

#endif /* DT_HARNESS_UTIL_H */
