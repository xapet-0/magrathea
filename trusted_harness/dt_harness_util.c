/* ************************************************************************** */
/*                                                                            */
/*   dt_harness_util.c                                                        */
/*   Magrathea Production Test Harness Utilities                              */
/*                                                                            */
/* ************************************************************************** */

#define _GNU_SOURCE
#include "dt_harness_util.h"

#include <dirent.h>
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

int dt_format_cat_e(const char *src, size_t src_len, char *dst, size_t dst_cap)
{
    if (!src || !dst || dst_cap == 0)
    {
        errno = EINVAL;
        return (-1);
    }
    size_t j = 0;
    for (size_t i = 0; i < src_len; i++)
    {
        char c = src[i];
        if (c == '\t')
        {
            if (j + 2 >= dst_cap)
            {
                errno = ENOSPC;
                dst[j] = '\0';
                return (-1);
            }
            dst[j++] = '^';
            dst[j++] = 'I';
        }
        else if (c == '\n')
        {
            if (j + 2 >= dst_cap)
            {
                errno = ENOSPC;
                dst[j] = '\0';
                return (-1);
            }
            dst[j++] = '$';
            dst[j++] = '\n';
        }
        else
        {
            if (j + 1 >= dst_cap)
            {
                errno = ENOSPC;
                dst[j] = '\0';
                return (-1);
            }
            dst[j++] = c;
        }
    }
    dst[j] = '\0';
    return (0);
}

int dt_truncate_output(
    const char *src,
    size_t      src_len,
    size_t      max_bytes,
    char       *dst,
    size_t      dst_cap,
    bool       *out_truncated
)
{
    if (!src || !dst || dst_cap == 0 || !out_truncated)
    {
        errno = EINVAL;
        return (-1);
    }
    const char *suffix = "\n...[Output truncated — Output limit exceeded]...\n";
    size_t suffix_len = strlen(suffix);
    if (src_len <= max_bytes)
    {
        if (src_len + 1 > dst_cap)
        {
            errno = ENOSPC;
            return (-1);
        }
        memcpy(dst, src, src_len);
        dst[src_len] = '\0';
        *out_truncated = false;
        return (0);
    }
    if (max_bytes + suffix_len + 1 > dst_cap)
    {
        errno = ENOSPC;
        return (-1);
    }
    memcpy(dst, src, max_bytes);
    memcpy(dst + max_bytes, suffix, suffix_len + 1);
    *out_truncated = true;
    return (0);
}

int dt_compare_return_and_output(
    int                     expected_rc,
    int                     actual_rc,
    const char             *expected_out,
    const char             *actual_out,
    dt_comparison_result_t *out
)
{
    if (!expected_out || !actual_out || !out)
    {
        errno = EINVAL;
        return (-1);
    }
    memset(out, 0, sizeof(*out));
    if (expected_rc != actual_rc)
        out->rc_mismatch = 1;

    size_t line = 1;
    size_t col = 1;
    size_t i = 0;
    while (expected_out[i] != '\0' && actual_out[i] != '\0')
    {
        if (expected_out[i] != actual_out[i])
        {
            out->output_mismatch = 1;
            out->diff_line = line;
            out->diff_col = col;
            break;
        }
        if (expected_out[i] == '\n')
        {
            line++;
            col = 1;
        }
        else
            col++;
        i++;
    }
    if (!out->output_mismatch && expected_out[i] != actual_out[i])
    {
        out->output_mismatch = 1;
        out->diff_line = line;
        out->diff_col = col;
    }
    out->matched = (out->rc_mismatch == 0 && out->output_mismatch == 0) ? 1 : 0;
    return (0);
}

int dt_aggregate_case_results(
    const dt_case_status_t *cases,
    size_t                  count,
    dt_suite_summary_t     *out_summary
)
{
    if (!out_summary || (count > 0 && !cases))
    {
        errno = EINVAL;
        return (-1);
    }
    memset(out_summary, 0, sizeof(*out_summary));
    if (count == 0)
    {
        /* Zero-Empty-Test Gate: 0 executed cases NEVER counts as passed */
        out_summary->all_passed = 0;
        return (0);
    }
    out_summary->total_cases = count;
    for (size_t i = 0; i < count; i++)
    {
        out_summary->total_duration_ms += cases[i].duration_ms;
        if (cases[i].timed_out)
        {
            out_summary->timeout_cases++;
            out_summary->failed_cases++;
        }
        else if (cases[i].passed && cases[i].returncode == 0)
            out_summary->passed_cases++;
        else
            out_summary->failed_cases++;
    }
    out_summary->all_passed = (out_summary->passed_cases == count) ? 1 : 0;
    return (0);
}

int dt_create_isolated_tempdir(
    const char *base_dir,
    const char *prefix,
    char       *out_path,
    size_t      out_cap
)
{
    if (!out_path || out_cap < 32)
    {
        errno = EINVAL;
        return (-1);
    }
    const char *base = (base_dir && base_dir[0]) ? base_dir : "/var/tmp";
    const char *pfx = (prefix && prefix[0]) ? prefix : "dt_tmp_";
    int n = snprintf(out_path, out_cap, "%s/%sXXXXXX", base, pfx);
    if (n < 0 || (size_t)n >= out_cap)
    {
        errno = ENAMETOOLONG;
        return (-1);
    }
    if (!mkdtemp(out_path))
        return (-1);
    if (chmod(out_path, 0700) != 0)
    {
        rmdir(out_path);
        return (-1);
    }
    return (0);
}

int dt_cleanup_tempdir(const char *dir_path)
{
    if (!dir_path || !dir_path[0] || strcmp(dir_path, "/") == 0)
    {
        errno = EINVAL;
        return (-1);
    }
    DIR *d = opendir(dir_path);
    if (!d)
        return (-1);
    struct dirent *ent;
    int rc = 0;
    while ((ent = readdir(d)) != NULL)
    {
        if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0)
            continue;
        char child[1024];
        int n = snprintf(child, sizeof(child), "%s/%s", dir_path, ent->d_name);
        if (n < 0 || (size_t)n >= sizeof(child))
        {
            rc = -1;
            continue;
        }
        struct stat st;
        if (lstat(child, &st) == 0)
        {
            if (S_ISDIR(st.st_mode))
            {
                if (dt_cleanup_tempdir(child) != 0)
                    rc = -1;
            }
            else if (unlink(child) != 0)
                rc = -1;
        }
    }
    closedir(d);
    if (rmdir(dir_path) != 0)
        rc = -1;
    return (rc);
}

int dt_capture_subprocess(
    char *const        argv[],
    const char        *stdin_data,
    int                timeout_ms,
    dt_proc_capture_t *out_cap
)
{
    if (!argv || !argv[0] || !out_cap)
    {
        errno = EINVAL;
        return (-1);
    }
    memset(out_cap, 0, sizeof(*out_cap));
    int limit_ms = (timeout_ms > 0) ? timeout_ms : 2000;

    int in_pipe[2] = {-1, -1};
    int out_pipe[2] = {-1, -1};
    int err_pipe[2] = {-1, -1};
    if (pipe(in_pipe) != 0 || pipe(out_pipe) != 0 || pipe(err_pipe) != 0)
    {
        if (in_pipe[0] >= 0) { close(in_pipe[0]); close(in_pipe[1]); }
        if (out_pipe[0] >= 0) { close(out_pipe[0]); close(out_pipe[1]); }
        return (-1);
    }

    pid_t pid = fork();
    if (pid < 0)
    {
        close(in_pipe[0]); close(in_pipe[1]);
        close(out_pipe[0]); close(out_pipe[1]);
        close(err_pipe[0]); close(err_pipe[1]);
        return (-1);
    }
    if (pid == 0)
    {
        setpgid(0, 0);
        close(in_pipe[1]);
        close(out_pipe[0]);
        close(err_pipe[0]);
        dup2(in_pipe[0], STDIN_FILENO);
        dup2(out_pipe[1], STDOUT_FILENO);
        dup2(err_pipe[1], STDERR_FILENO);
        close(in_pipe[0]);
        close(out_pipe[1]);
        close(err_pipe[1]);
        execvp(argv[0], argv);
        _exit(127);
    }

    close(in_pipe[0]);
    close(out_pipe[1]);
    close(err_pipe[1]);

    if (stdin_data && stdin_data[0] != '\0')
    {
        size_t slen = strlen(stdin_data);
        ssize_t unused = write(in_pipe[1], stdin_data, slen);
        (void)unused;
    }
    close(in_pipe[1]);

    fcntl(out_pipe[0], F_SETFL, O_NONBLOCK);
    fcntl(err_pipe[0], F_SETFL, O_NONBLOCK);

    struct timespec t0;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    int wstatus = 0;
    bool done = false;

    while (!done)
    {
        struct pollfd pfds[2] = {
            {.fd = out_pipe[0], .events = POLLIN},
            {.fd = err_pipe[0], .events = POLLIN}
        };
        poll(pfds, 2, 5);
        char buf[512];
        ssize_t r;
        while ((r = read(out_pipe[0], buf, sizeof(buf))) > 0)
        {
            if (out_cap->stdout_len + 1 < sizeof(out_cap->stdout_buf))
            {
                size_t n = (size_t)r;
                if (out_cap->stdout_len + n >= sizeof(out_cap->stdout_buf))
                    n = sizeof(out_cap->stdout_buf) - out_cap->stdout_len - 1;
                memcpy(out_cap->stdout_buf + out_cap->stdout_len, buf, n);
                out_cap->stdout_len += n;
                out_cap->stdout_buf[out_cap->stdout_len] = '\0';
            }
        }
        while ((r = read(err_pipe[0], buf, sizeof(buf))) > 0)
        {
            if (out_cap->stderr_len + 1 < sizeof(out_cap->stderr_buf))
            {
                size_t n = (size_t)r;
                if (out_cap->stderr_len + n >= sizeof(out_cap->stderr_buf))
                    n = sizeof(out_cap->stderr_buf) - out_cap->stderr_len - 1;
                memcpy(out_cap->stderr_buf + out_cap->stderr_len, buf, n);
                out_cap->stderr_len += n;
                out_cap->stderr_buf[out_cap->stderr_len] = '\0';
            }
        }

        pid_t w = waitpid(pid, &wstatus, WNOHANG);
        if (w == pid)
        {
            done = true;
            break;
        }
        struct timespec now;
        clock_gettime(CLOCK_MONOTONIC, &now);
        long elapsed_ms = (now.tv_sec - t0.tv_sec) * 1000L + (now.tv_nsec - t0.tv_nsec) / 1000000L;
        if (elapsed_ms >= limit_ms)
        {
            out_cap->timed_out = 1;
            kill(-pid, SIGKILL);
            kill(pid, SIGKILL);
            waitpid(pid, &wstatus, 0);
            done = true;
        }
    }

    /* Final drain after process exit */
    char buf[512];
    ssize_t r;
    while ((r = read(out_pipe[0], buf, sizeof(buf))) > 0)
    {
        if (out_cap->stdout_len + 1 < sizeof(out_cap->stdout_buf))
        {
            size_t n = (size_t)r;
            if (out_cap->stdout_len + n >= sizeof(out_cap->stdout_buf))
                n = sizeof(out_cap->stdout_buf) - out_cap->stdout_len - 1;
            memcpy(out_cap->stdout_buf + out_cap->stdout_len, buf, n);
            out_cap->stdout_len += n;
            out_cap->stdout_buf[out_cap->stdout_len] = '\0';
        }
    }
    while ((r = read(err_pipe[0], buf, sizeof(buf))) > 0)
    {
        if (out_cap->stderr_len + 1 < sizeof(out_cap->stderr_buf))
        {
            size_t n = (size_t)r;
            if (out_cap->stderr_len + n >= sizeof(out_cap->stderr_buf))
                n = sizeof(out_cap->stderr_buf) - out_cap->stderr_len - 1;
            memcpy(out_cap->stderr_buf + out_cap->stderr_len, buf, n);
            out_cap->stderr_len += n;
            out_cap->stderr_buf[out_cap->stderr_len] = '\0';
        }
    }
    close(out_pipe[0]);
    close(err_pipe[0]);
    kill(-pid, SIGKILL);

    if (out_cap->timed_out)
        out_cap->signed_returncode = -SIGKILL;
    else if (WIFSIGNALED(wstatus))
        out_cap->signed_returncode = -WTERMSIG(wstatus);
    else if (WIFEXITED(wstatus))
        out_cap->signed_returncode = WEXITSTATUS(wstatus);
    else
        out_cap->signed_returncode = -1;
    return (0);
}

int dt_serialize_harness_report_json(
    const dt_suite_summary_t *summary,
    char                     *out_json,
    size_t                    json_cap
)
{
    if (!summary || !out_json || json_cap < 64)
    {
        errno = EINVAL;
        return (-1);
    }
    int n = snprintf(
        out_json,
        json_cap,
        "{\"total_cases\":%zu,\"passed_cases\":%zu,\"failed_cases\":%zu,"
        "\"timeout_cases\":%zu,\"all_passed\":%s,\"total_duration_ms\":%.3f}",
        summary->total_cases,
        summary->passed_cases,
        summary->failed_cases,
        summary->timeout_cases,
        summary->all_passed ? "true" : "false",
        summary->total_duration_ms
    );
    if (n < 0 || (size_t)n >= json_cap)
    {
        errno = ENOSPC;
        return (-1);
    }
    return (0);
}
