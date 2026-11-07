/* ************************************************************************** */
/*                                                                            */
/*   dt_diagnostics.c                                                         */
/*   Magrathea Production Exit-Status, Signal & Memory Diagnostic Classifier  */
/*                                                                            */
/* ************************************************************************** */

#define _GNU_SOURCE
#include "dt_diagnostics.h"

#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>

static bool dt_stderr_has(const char *stderr_text, const char *needle)
{
    if (!stderr_text || !needle)
        return (false);
    return (strstr(stderr_text, needle) != NULL);
}

const char *dt_diag_kind_name(dt_diag_kind_t kind)
{
    switch (kind)
    {
        case DT_DIAG_OK:                    return ("OK");
        case DT_DIAG_NONZERO_EXIT:          return ("NONZERO_EXIT");
        case DT_DIAG_SIGABRT:               return ("SIGABRT");
        case DT_DIAG_SIGSEGV:               return ("SIGSEGV");
        case DT_DIAG_SIGBUS:                return ("SIGBUS");
        case DT_DIAG_SIGFPE:                return ("SIGFPE");
        case DT_DIAG_OTHER_SIGNAL:          return ("OTHER_SIGNAL");
        case DT_DIAG_TIMEOUT:               return ("TIMEOUT");
        case DT_DIAG_LEAK_KO:               return ("LEAK_KO");
        case DT_DIAG_REDZONE_KO:            return ("REDZONE_KO");
        case DT_DIAG_INVALID_FREE_KO:       return ("INVALID_FREE_KO");
        case DT_DIAG_ARENA_OWNERSHIP_KO:    return ("ARENA_OWNERSHIP_KO");
        case DT_DIAG_TRACKING_EXHAUSTED_KO: return ("TRACKING_EXHAUSTED_KO");
        case DT_DIAG_DOUBLE_FREE_KO:        return ("DOUBLE_FREE_KO");
        case DT_DIAG_COMPILE_FAILURE:       return ("COMPILE_FAILURE");
        case DT_DIAG_OUTPUT_LIMIT:          return ("OUTPUT_LIMIT");
        default:                            return ("UNKNOWN");
    }
}

bool dt_diag_is_signal(const dt_diag_result_t *res)
{
    if (!res)
        return (false);
    return (res->is_signal != 0 && res->signal_number > 0);
}

bool dt_diag_is_memory_violation(const dt_diag_result_t *res)
{
    if (!res)
        return (false);
    return (res->is_memory_error != 0);
}

int dt_diag_classify_execution(
    int               signed_returncode,
    int               timed_out,
    int               compile_failed,
    int               output_exceeded,
    const char       *stderr_text,
    dt_diag_result_t *out
)
{
    if (!out)
    {
        errno = EINVAL;
        return (-1);
    }
    memset(out, 0, sizeof(*out));

    if (compile_failed)
    {
        out->kind = DT_DIAG_COMPILE_FAILURE;
        out->exit_code = signed_returncode;
        snprintf(out->status_label, sizeof(out->status_label), "Does not compile");
        snprintf(out->reason_detail, sizeof(out->reason_detail), "Compilation or linking failed");
        return (0);
    }

    if (timed_out)
    {
        out->kind = DT_DIAG_TIMEOUT;
        out->exit_code = signed_returncode;
        snprintf(out->status_label, sizeof(out->status_label), "Timeout");
        snprintf(out->reason_detail, sizeof(out->reason_detail), "Command killed by timeout");
        return (0);
    }

    if (output_exceeded)
    {
        out->kind = DT_DIAG_OUTPUT_LIMIT;
        out->exit_code = signed_returncode;
        snprintf(out->status_label, sizeof(out->status_label), "Output limit exceeded (>64 KB)");
        snprintf(out->reason_detail, sizeof(out->reason_detail), "Output limit exceeded");
        return (0);
    }

    if (signed_returncode == 0)
    {
        out->kind = DT_DIAG_OK;
        out->exit_code = 0;
        snprintf(out->status_label, sizeof(out->status_label), "OK :)");
        snprintf(out->reason_detail, sizeof(out->reason_detail), "OK :)");
        return (0);
    }

    /* Negative returncode strictly denotes signal termination (-signum).
     * Positive returncode strictly denotes normal process exit (_exit(code)). */
    if (signed_returncode < 0)
    {
        int sig = -signed_returncode;
        out->is_signal = 1;
        out->signal_number = sig;
        out->exit_code = signed_returncode;

        if (sig == SIGABRT)
        {
            if (dt_stderr_has(stderr_text, "[DOUBLE FREE KO]"))
            {
                out->kind = DT_DIAG_DOUBLE_FREE_KO;
                out->is_memory_error = 1;
                snprintf(out->status_label, sizeof(out->status_label), "Double/Invalid Free KO (abort)");
                snprintf(out->reason_detail, sizeof(out->reason_detail), "Double free detected by memory harness");
            }
            else
            {
                out->kind = DT_DIAG_SIGABRT;
                snprintf(out->status_label, sizeof(out->status_label), "Abort (Signal -6)");
                snprintf(out->reason_detail, sizeof(out->reason_detail), "Process terminated by SIGABRT (Signal -6)");
            }
            return (0);
        }
        if (sig == SIGSEGV)
        {
            out->kind = DT_DIAG_SIGSEGV;
            snprintf(out->status_label, sizeof(out->status_label), "Segmentation fault (Signal -11)");
            snprintf(out->reason_detail, sizeof(out->reason_detail), "Process terminated by SIGSEGV (Signal -11)");
            return (0);
        }
        if (sig == SIGBUS)
        {
            out->kind = DT_DIAG_SIGBUS;
            snprintf(out->status_label, sizeof(out->status_label), "Bus error (Signal -7)");
            snprintf(out->reason_detail, sizeof(out->reason_detail), "Process terminated by SIGBUS (Signal -7)");
            return (0);
        }
        if (sig == SIGFPE)
        {
            out->kind = DT_DIAG_SIGFPE;
            snprintf(out->status_label, sizeof(out->status_label), "Floating point exception (Signal -8)");
            snprintf(out->reason_detail, sizeof(out->reason_detail), "Process terminated by SIGFPE (Signal -8)");
            return (0);
        }
        out->kind = DT_DIAG_OTHER_SIGNAL;
        snprintf(out->status_label, sizeof(out->status_label), "Signal -%d", sig);
        snprintf(out->reason_detail, sizeof(out->reason_detail), "Process terminated by Signal -%d", sig);
        return (0);
    }

    /* Positive exit codes (1..255) */
    out->is_signal = 0;
    out->signal_number = 0;
    out->exit_code = signed_returncode;

    if (signed_returncode == 42)
    {
        out->kind = DT_DIAG_LEAK_KO;
        out->is_memory_error = 1;
        snprintf(out->status_label, sizeof(out->status_label), "Leak KO (memory leak detected)");
        snprintf(out->reason_detail, sizeof(out->reason_detail), "Unfreed heap memory blocks detected at exit");
        return (0);
    }
    if (signed_returncode == 43)
    {
        out->kind = DT_DIAG_REDZONE_KO;
        out->is_memory_error = 1;
        snprintf(out->status_label, sizeof(out->status_label), "Redzone KO (heap buffer overflow / off-by-one)");
        snprintf(out->reason_detail, sizeof(out->reason_detail), "Heap redzone canary corruption detected");
        return (0);
    }
    if (signed_returncode == 44)
    {
        out->is_memory_error = 1;
        if (dt_stderr_has(stderr_text, "[ARENA OWNERSHIP KO]"))
        {
            out->kind = DT_DIAG_ARENA_OWNERSHIP_KO;
            snprintf(out->status_label, sizeof(out->status_label), "Invalid Free KO (arena ownership violation)");
            snprintf(out->reason_detail, sizeof(out->reason_detail), "Student attempted to free/realloc harness arena pointer");
        }
        else
        {
            out->kind = DT_DIAG_INVALID_FREE_KO;
            snprintf(out->status_label, sizeof(out->status_label), "Invalid Free KO (untracked or misaligned pointer)");
            snprintf(out->reason_detail, sizeof(out->reason_detail), "Attempted to free untracked or misaligned pointer");
        }
        return (0);
    }
    if (signed_returncode == 45)
    {
        out->kind = DT_DIAG_TRACKING_EXHAUSTED_KO;
        out->is_memory_error = 1;
        snprintf(out->status_label, sizeof(out->status_label), "Allocation Tracking Exhausted KO");
        snprintf(out->reason_detail, sizeof(out->reason_detail), "Allocation tracking capacity exceeded");
        return (0);
    }
    if (signed_returncode == 46 || (signed_returncode == 6 && dt_stderr_has(stderr_text, "[DOUBLE FREE KO]")))
    {
        out->kind = DT_DIAG_DOUBLE_FREE_KO;
        out->is_memory_error = 1;
        snprintf(out->status_label, sizeof(out->status_label), "Double/Invalid Free KO (abort)");
        snprintf(out->reason_detail, sizeof(out->reason_detail), "Double free detected by memory harness");
        return (0);
    }

    /* All other positive exit codes (including 6 without [DOUBLE FREE KO], 7, 8, 11)
     * are normal nonzero exits, NEVER signals! */
    out->kind = DT_DIAG_NONZERO_EXIT;
    snprintf(out->status_label, sizeof(out->status_label), "Exit %d", signed_returncode);
    snprintf(out->reason_detail, sizeof(out->reason_detail), "Non-zero exit code %d", signed_returncode);
    return (0);
}

int dt_diag_from_wait_status(
    int               raw_wstatus,
    int               timed_out,
    const char       *stderr_text,
    dt_diag_result_t *out
)
{
    if (!out)
    {
        errno = EINVAL;
        return (-1);
    }
    if (timed_out)
        return (dt_diag_classify_execution(-SIGKILL, 1, 0, 0, stderr_text, out));
    if (WIFSIGNALED(raw_wstatus))
    {
        int sig = WTERMSIG(raw_wstatus);
        return (dt_diag_classify_execution(-sig, 0, 0, 0, stderr_text, out));
    }
    if (WIFEXITED(raw_wstatus))
    {
        int ec = WEXITSTATUS(raw_wstatus);
        return (dt_diag_classify_execution(ec, 0, 0, 0, stderr_text, out));
    }
    errno = EINVAL;
    return (-1);
}
