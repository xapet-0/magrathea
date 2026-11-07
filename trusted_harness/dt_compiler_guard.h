/* ************************************************************************** */
/*                                                                            */
/*   dt_compiler_guard.h                                                      */
/*   Magrathea Production C Compiler Guard, Lexical Scanner & ELF Verifier    */
/*   - Strips C comments and string/char literals                             */
/*   - Detects forbidden #include (.c, /abs, ../parent, macro-computed)       */
/*   - Detects forbidden inline assembly and forbidden main()                 */
/*   - Normalizes ELF/Mach-O symbol names against glibc/ABI tables            */
/*   - Verifies compiled ELF object provenance (non-stale mtime + \x7fELF)    */
/*   - Invokes real C compiler subprocess with timeout & stderr capture       */
/*                                                                            */
/* ************************************************************************** */

#ifndef DT_COMPILER_GUARD_H
#define DT_COMPILER_GUARD_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct s_dt_include_scan {
    int  dot_c_includes;
    int  path_traversal_includes;
    int  macro_computed_includes;
    int  total_violations;
    char first_violation[128];
} dt_include_scan_t;

typedef struct s_dt_compile_job {
    const char *cc_binary;
    const char *source_path;
    const char *extra_source_path;
    const char *output_path;
    const char *include_dir;
    int         compile_only;
    int         warnings_as_errors;
    int         timeout_ms;
} dt_compile_job_t;

typedef struct s_dt_compile_outcome {
    int    ok;
    int    returncode;
    int    timed_out;
    int    provenance_verified;
    size_t output_file_size;
    char   stderr_text[2048];
} dt_compile_outcome_t;

int dt_strip_c_comments_and_strings(const char *src, char *dst, size_t dst_cap);
int dt_scan_include_restrictions(const char *src, dt_include_scan_t *out_scan);
int dt_detect_forbidden_constructs(const char *src, bool *out_has_asm, bool *out_has_main);
int dt_normalize_elf_symbol(const char *raw_sym, char *out_canonical, size_t cap, bool *out_is_intrinsic);
int dt_verify_elf_object_provenance(const char *obj_path, uint64_t min_mtime_sec, size_t *out_file_size);
int dt_compile_and_link_c(const dt_compile_job_t *job, dt_compile_outcome_t *out);

#ifdef __cplusplus
}
#endif

#endif /* DT_COMPILER_GUARD_H */
