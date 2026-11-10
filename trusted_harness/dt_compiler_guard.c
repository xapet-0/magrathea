/* ************************************************************************** */
/*                                                                            */
/*   dt_compiler_guard.c                                                      */
/*   Magrathea Production C Compiler Guard, Lexical Scanner & ELF Verifier    */
/*                                                                            */
/* ************************************************************************** */

#define _GNU_SOURCE
#include "dt_compiler_guard.h"

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

int dt_strip_c_comments_and_strings(const char *src, char *dst, size_t dst_cap)
{
    if (!src || !dst || dst_cap == 0)
    {
        errno = EINVAL;
        return (-1);
    }
    size_t i = 0;
    size_t j = 0;
    while (src[i] != '\0' && j + 1 < dst_cap)
    {
        /* Line comment //... */
        if (src[i] == '/' && src[i + 1] == '/')
        {
            i += 2;
            while (src[i] != '\0' && src[i] != '\n')
                i++;
            dst[j++] = ' ';
            continue;
        }
        /* Block comment / * ... * / */
        if (src[i] == '/' && src[i + 1] == '*')
        {
            i += 2;
            while (src[i] != '\0' && !(src[i] == '*' && src[i + 1] == '/'))
            {
                if (src[i] == '\n' && j + 1 < dst_cap)
                    dst[j++] = '\n';
                i++;
            }
            if (src[i] != '\0')
                i += 2;
            if (j + 1 < dst_cap)
                dst[j++] = ' ';
            continue;
        }
        /* String or char literal */
        if (src[i] == '"' || src[i] == '\'')
        {
            char quote = src[i++];
            while (src[i] != '\0' && src[i] != quote)
            {
                if (src[i] == '\\' && src[i + 1] != '\0')
                    i += 2;
                else
                    i++;
            }
            if (src[i] == quote)
                i++;
            dst[j++] = ' ';
            continue;
        }
        dst[j++] = src[i++];
    }
    dst[j] = '\0';
    return (0);
}

/**
 * dt_prepare_source_for_include_scan() - Normalize C source before #include scanning.
 * @src: Null-terminated raw C source string.
 *
 * Joins Phase-2 backslash-newline (\\\n) line continuations and strips C line
 * and block comments while preserving string literals on preprocessor directive
 * lines so inline comments cannot mask forbidden #include directives.
 *
 * Context: Safe to call from any thread; allocates a caller-freed heap buffer.
 * Return: Newly allocated normalized string on success, or NULL on OOM.
 */
static char *dt_prepare_source_for_include_scan(const char *src)
{
    size_t len = strlen(src);
    char *spliced = (char *)malloc(len + 1);
    char *cleaned = (char *)malloc(len + 1);
    if (!spliced || !cleaned)
    {
        free(spliced);
        free(cleaned);
        return (NULL);
    }
    /* 1. Join backslash-newline line continuations */
    size_t si = 0, sj = 0;
    while (src[si] != '\0')
    {
        if (src[si] == '\\' && src[si + 1] == '\n')
        {
            si += 2;
            continue;
        }
        if (src[si] == '\\' && src[si + 1] == '\r' && src[si + 2] == '\n')
        {
            si += 3;
            continue;
        }
        spliced[sj++] = src[si++];
    }
    spliced[sj] = '\0';
    /* 2. Strip line and block comments while preserving string literals on #include lines */
    size_t i = 0, j = 0;
    bool at_line_head = true;
    bool in_directive = false;
    while (spliced[i] != '\0')
    {
        if (spliced[i] == '\n')
        {
            cleaned[j++] = spliced[i++];
            at_line_head = true;
            in_directive = false;
            continue;
        }
        if (spliced[i] == '/' && spliced[i + 1] == '/')
        {
            i += 2;
            while (spliced[i] != '\0' && spliced[i] != '\n')
                i++;
            cleaned[j++] = ' ';
            continue;
        }
        if (spliced[i] == '/' && spliced[i + 1] == '*')
        {
            i += 2;
            while (spliced[i] != '\0' && !(spliced[i] == '*' && spliced[i + 1] == '/'))
            {
                if (spliced[i] == '\n')
                {
                    cleaned[j++] = '\n';
                    at_line_head = true;
                    in_directive = false;
                }
                i++;
            }
            if (spliced[i] != '\0')
                i += 2;
            cleaned[j++] = ' ';
            continue;
        }
        if (!in_directive && (spliced[i] == '"' || spliced[i] == '\''))
        {
            char q = spliced[i++];
            while (spliced[i] != '\0' && spliced[i] != q)
            {
                if (spliced[i] == '\\' && spliced[i + 1] != '\0')
                    i += 2;
                else
                    i++;
            }
            if (spliced[i] == q)
                i++;
            cleaned[j++] = ' ';
            continue;
        }
        if (at_line_head && spliced[i] != ' ' && spliced[i] != '\t')
        {
            if (spliced[i] == '#')
                in_directive = true;
            at_line_head = false;
        }
        cleaned[j++] = spliced[i++];
    }
    cleaned[j] = '\0';
    free(spliced);
    return (cleaned);
}

int dt_scan_include_restrictions(const char *src, dt_include_scan_t *out_scan)
{
    if (!src || !out_scan)
    {
        errno = EINVAL;
        return (-1);
    }
    memset(out_scan, 0, sizeof(*out_scan));
    char *prepped = dt_prepare_source_for_include_scan(src);
    const char *p = prepped ? prepped : src;
    while (*p != '\0')
    {
        const char *line_start = p;
        const char *line_end = strchr(p, '\n');
        size_t line_len = line_end ? (size_t)(line_end - line_start) : strlen(line_start);

        const char *cur = line_start;
        const char *limit = line_start + line_len;
        while (cur < limit && (*cur == ' ' || *cur == '\t'))
            cur++;
        if (cur < limit && *cur == '#')
        {
            cur++;
            while (cur < limit && (*cur == ' ' || *cur == '\t'))
                cur++;
            if ((size_t)(limit - cur) >= 7 && strncmp(cur, "include", 7) == 0 && (cur + 7 == limit || !isalnum((unsigned char)cur[7])))
            {
                cur += 7;
                while (cur < limit && (*cur == ' ' || *cur == '\t'))
                    cur++;
                if (cur < limit && (*cur == '"' || *cur == '<'))
                {
                    char close_ch = (*cur == '<') ? '>' : '"';
                    cur++;
                    const char *target_start = cur;
                    while (cur < limit && *cur != close_ch)
                        cur++;
                    size_t target_len = (size_t)(cur - target_start);
                    if (target_len >= 2 && strncmp(target_start + target_len - 2, ".c", 2) == 0)
                    {
                        out_scan->dot_c_includes++;
                        out_scan->total_violations++;
                        if (out_scan->first_violation[0] == '\0')
                            snprintf(out_scan->first_violation, sizeof(out_scan->first_violation), "forbidden .c include");
                    }
                    bool has_dotdot = false;
                    for (size_t k = 0; k + 2 <= target_len; k++)
                    {
                        if (target_start[k] == '.' && target_start[k + 1] == '.' &&
                            (k + 2 == target_len || target_start[k + 2] == '/' || target_start[k + 2] == '\\'))
                        {
                            has_dotdot = true;
                            break;
                        }
                    }
                    if ((target_len >= 1 && (target_start[0] == '/' || target_start[0] == '\\')) || has_dotdot)
                    {
                        out_scan->path_traversal_includes++;
                        out_scan->total_violations++;
                        if (out_scan->first_violation[0] == '\0')
                            snprintf(out_scan->first_violation, sizeof(out_scan->first_violation), "forbidden path include");
                    }
                }
                else if (cur < limit && (isalpha((unsigned char)*cur) || *cur == '_'))
                {
                    out_scan->macro_computed_includes++;
                    out_scan->total_violations++;
                    if (out_scan->first_violation[0] == '\0')
                        snprintf(out_scan->first_violation, sizeof(out_scan->first_violation), "forbidden macro-computed include");
                }
            }
        }
        p = line_end ? (line_end + 1) : (line_start + line_len);
    }
    free(prepped);
    return (0);
}

static bool dt_contains_identifier(const char *cleaned, const char *ident, bool require_open_paren)
{
    size_t len = strlen(ident);
    const char *p = cleaned;
    while ((p = strstr(p, ident)) != NULL)
    {
        bool left_ok = (p == cleaned) || (!isalnum((unsigned char)p[-1]) && p[-1] != '_');
        const char *after = p + len;
        bool right_ok = (!isalnum((unsigned char)*after) && *after != '_');
        if (left_ok && right_ok)
        {
            if (!require_open_paren)
                return (true);
            while (*after == ' ' || *after == '\t' || *after == '\n' || *after == '\r')
                after++;
            if (*after == '(')
                return (true);
        }
        p += len;
    }
    return (false);
}

int dt_detect_forbidden_constructs(const char *src, bool *out_has_asm, bool *out_has_main)
{
    if (!src || !out_has_asm || !out_has_main)
    {
        errno = EINVAL;
        return (-1);
    }
    size_t cap = strlen(src) + 2;
    char *cleaned = (char *)malloc(cap);
    if (!cleaned)
    {
        errno = ENOMEM;
        return (-1);
    }
    dt_strip_c_comments_and_strings(src, cleaned, cap);
    *out_has_asm = (
        dt_contains_identifier(cleaned, "asm", false)
        || dt_contains_identifier(cleaned, "__asm", false)
        || dt_contains_identifier(cleaned, "__asm__", false)
    );
    *out_has_main = dt_contains_identifier(cleaned, "main", true);
    free(cleaned);
    return (0);
}

typedef struct s_sym_alias {
    const char *raw;
    const char *canonical;
} t_sym_alias;

static const char *const g_intrinsic_syms[] = {
    "stdin", "stdout", "stderr", "__stdin", "__stdout", "__stderr",
    "___stack_chk_fail", "__stack_chk_fail", "_stack_chk_fail", "stack_chk_fail",
    "___stack_chk_guard", "__stack_chk_guard", "_stack_chk_guard", "stack_chk_guard",
    "__gmon_start__", "gmon_start__",
    "_ITM_deregisterTMCloneTable", "_ITM_registerTMCloneTable",
    "__cxa_finalize", "__cxa_atexit", "__libc_start_main",
    "_GLOBAL_OFFSET_TABLE_", "mcount", "__fentry__", "__dso_handle",
    "__TMC_END__", "__data_start", "__bss_start",
    "__addvsi3", "__subvsi3", "__mulvsi3", "__negvsi2", "__absvsi2",
    "__addvdi3", "__subvdi3", "__mulvdi3", "__negvdi2", "__absvdi2",
    NULL
};

static const t_sym_alias g_glibc_aliases[] = {
    {"__ctype_b_loc", "isdigit"},
    {"__ctype_tolower_loc", "tolower"},
    {"__ctype_toupper_loc", "toupper"},
    {"__isoc99_scanf", "scanf"},
    {"__isoc23_scanf", "scanf"},
    {"__isoc99_fscanf", "fscanf"},
    {"__isoc99_sscanf", "sscanf"},
    {"__printf_chk", "printf"},
    {"__fprintf_chk", "fprintf"},
    {"__sprintf_chk", "sprintf"},
    {"__snprintf_chk", "snprintf"},
    {"__memcpy_chk", "memcpy"},
    {"__memmove_chk", "memmove"},
    {"__memset_chk", "memset"},
    {"__libc_malloc", "malloc"},
    {"__libc_free", "free"},
    {"__libc_calloc", "calloc"},
    {"__libc_realloc", "realloc"},
    {"__libc_write", "write"},
    {"__libc_read", "read"},
    {"__errno_location", "errno"},
    {"__error", "errno"},
    {NULL, NULL}
};

static bool dt_is_intrinsic_name(const char *s)
{
    if (strncmp(s, "_GLOBAL_", 8) == 0 || strncmp(s, "_ITM_", 5) == 0 || strncmp(s, "dyld_", 5) == 0)
        return (true);
    for (size_t i = 0; g_intrinsic_syms[i] != NULL; i++)
    {
        if (strcmp(s, g_intrinsic_syms[i]) == 0)
            return (true);
    }
    return (false);
}

static const char *dt_lookup_alias(const char *s)
{
    for (size_t i = 0; g_glibc_aliases[i].raw != NULL; i++)
    {
        if (strcmp(s, g_glibc_aliases[i].raw) == 0)
            return (g_glibc_aliases[i].canonical);
    }
    return (NULL);
}

int dt_normalize_elf_symbol(const char *raw_sym, char *out_canonical, size_t cap, bool *out_is_intrinsic)
{
    if (!raw_sym || !raw_sym[0] || !out_canonical || cap == 0 || !out_is_intrinsic)
    {
        errno = EINVAL;
        return (-1);
    }
    char stripped[128];
    size_t i = 0;
    while (raw_sym[i] != '\0' && raw_sym[i] != '@' && i + 1 < sizeof(stripped))
    {
        stripped[i] = raw_sym[i];
        i++;
    }
    stripped[i] = '\0';

    if (dt_is_intrinsic_name(stripped))
    {
        *out_is_intrinsic = true;
        snprintf(out_canonical, cap, "%s", stripped);
        return (0);
    }
    const char *aliased = dt_lookup_alias(stripped);
    if (aliased)
    {
        *out_is_intrinsic = false;
        snprintf(out_canonical, cap, "%s", aliased);
        return (0);
    }
    const char *cand = (stripped[0] == '_' && stripped[1] != '_' && stripped[1] != '\0') ? (stripped + 1) : stripped;
    if (dt_is_intrinsic_name(cand))
    {
        *out_is_intrinsic = true;
        snprintf(out_canonical, cap, "%s", cand);
        return (0);
    }
    aliased = dt_lookup_alias(cand);
    if (aliased)
    {
        *out_is_intrinsic = false;
        snprintf(out_canonical, cap, "%s", aliased);
        return (0);
    }
    *out_is_intrinsic = false;
    snprintf(out_canonical, cap, "%s", cand);
    return (0);
}

int dt_verify_elf_object_provenance(const char *obj_path, uint64_t min_mtime_sec, size_t *out_file_size)
{
    if (!obj_path || !obj_path[0])
    {
        errno = EINVAL;
        return (-1);
    }
    struct stat st;
    if (stat(obj_path, &st) != 0 || !S_ISREG(st.st_mode) || st.st_size < 16)
        return (-1);
    if ((uint64_t)st.st_mtime < min_mtime_sec)
        return (-1);
    int fd = open(obj_path, O_RDONLY);
    if (fd < 0)
        return (-1);
    unsigned char magic[4] = {0, 0, 0, 0};
    ssize_t n = read(fd, magic, 4);
    close(fd);
    if (n != 4 || magic[0] != 0x7f || magic[1] != 'E' || magic[2] != 'L' || magic[3] != 'F')
        return (-1);
    if (out_file_size)
        *out_file_size = (size_t)st.st_size;
    return (0);
}

int dt_compile_and_link_c(const dt_compile_job_t *job, dt_compile_outcome_t *out)
{
    if (!job || !job->source_path || !job->output_path || !out)
    {
        errno = EINVAL;
        return (-1);
    }
    memset(out, 0, sizeof(*out));
    const char *cc = (job->cc_binary && job->cc_binary[0]) ? job->cc_binary : "cc";
    int timeout_ms = (job->timeout_ms > 0) ? job->timeout_ms : 5000;

    uint64_t start_sec = (uint64_t)time(NULL);
    unlink(job->output_path);

    int err_pipe[2];
    if (pipe(err_pipe) != 0)
        return (-1);

    pid_t pid = fork();
    if (pid < 0)
    {
        close(err_pipe[0]);
        close(err_pipe[1]);
        return (-1);
    }
    if (pid == 0)
    {
        setpgid(0, 0);
        close(err_pipe[0]);
        dup2(err_pipe[1], STDERR_FILENO);
        dup2(err_pipe[1], STDOUT_FILENO);
        close(err_pipe[1]);

        const char *argv[20];
        int k = 0;
        argv[k++] = cc;
        argv[k++] = "-Wall";
        argv[k++] = "-Wextra";
        if (job->warnings_as_errors)
            argv[k++] = "-Werror";
        if (job->include_dir && job->include_dir[0])
        {
            argv[k++] = "-I";
            argv[k++] = job->include_dir;
        }
        if (job->compile_only)
            argv[k++] = "-c";
        argv[k++] = job->source_path;
        if (job->extra_source_path && job->extra_source_path[0])
            argv[k++] = job->extra_source_path;
        argv[k++] = "-o";
        argv[k++] = job->output_path;
        argv[k] = NULL;

        execvp(cc, (char *const *)argv);
        fprintf(stderr, "execvp(%s) failed: %s\n", cc, strerror(errno));
        _exit(127);
    }

    close(err_pipe[1]);
    fcntl(err_pipe[0], F_SETFL, O_NONBLOCK);

    struct timespec t0;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    size_t err_used = 0;
    int wstatus = 0;
    bool child_done = false;

    while (!child_done)
    {
        struct pollfd pfd = {.fd = err_pipe[0], .events = POLLIN};
        poll(&pfd, 1, 5);
        if (pfd.revents & (POLLIN | POLLHUP))
        {
            char buf[512];
            ssize_t r = read(err_pipe[0], buf, sizeof(buf));
            if (r > 0 && err_used + 1 < sizeof(out->stderr_text))
            {
                size_t copy_n = (size_t)r;
                if (err_used + copy_n >= sizeof(out->stderr_text))
                    copy_n = sizeof(out->stderr_text) - err_used - 1;
                memcpy(out->stderr_text + err_used, buf, copy_n);
                err_used += copy_n;
                out->stderr_text[err_used] = '\0';
            }
        }
        pid_t w = waitpid(pid, &wstatus, WNOHANG);
        if (w == pid)
        {
            child_done = true;
            break;
        }
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        long elapsed_ms = (now.tv_sec - t0.tv_sec) * 1000L + (now.tv_nsec - t0.tv_nsec) / 1000000L;
        if (elapsed_ms >= timeout_ms)
        {
            out->timed_out = 1;
            kill(-pid, SIGKILL);
            kill(pid, SIGKILL);
            waitpid(pid, &wstatus, 0);
            child_done = true;
        }
    }
    /* Drain remaining pipe bytes */
    char drain[256];
    ssize_t dr;
    while ((dr = read(err_pipe[0], drain, sizeof(drain))) > 0)
    {
        if (err_used + 1 < sizeof(out->stderr_text))
        {
            size_t copy_n = (size_t)dr;
            if (err_used + copy_n >= sizeof(out->stderr_text))
                copy_n = sizeof(out->stderr_text) - err_used - 1;
            memcpy(out->stderr_text + err_used, drain, copy_n);
            err_used += copy_n;
            out->stderr_text[err_used] = '\0';
        }
    }
    close(err_pipe[0]);

    if (out->timed_out)
    {
        out->ok = 0;
        out->returncode = -SIGKILL;
        return (0);
    }
    if (WIFEXITED(wstatus))
        out->returncode = WEXITSTATUS(wstatus);
    else if (WIFSIGNALED(wstatus))
        out->returncode = -WTERMSIG(wstatus);
    else
        out->returncode = -1;

    if (out->returncode == 0)
    {
        size_t fsz = 0;
        if (dt_verify_elf_object_provenance(job->output_path, start_sec > 0 ? start_sec - 1 : 0, &fsz) == 0)
        {
            out->ok = 1;
            out->provenance_verified = 1;
            out->output_file_size = fsz;
        }
        else
        {
            out->ok = 0;
            out->provenance_verified = 0;
        }
    }
    return (0);
}
