#include <stdbool.h>
#include <unistd.h>
#include <sys/wait.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>

static void noop_handler(int sig) { (void)sig; }

int sandbox(void (*f)(void), unsigned int timeout, bool verbose)
{
    pid_t pid = fork();
    if (pid < 0) return -1;
    if (pid == 0) {
        alarm(timeout);
        f();
        exit(0);
    }
    struct sigaction sa;
    sa.sa_handler = noop_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    sigaction(SIGALRM, &sa, NULL);
    alarm(timeout);
    int status = 0;
    pid_t r = waitpid(pid, &status, 0);
    alarm(0);
    if (r < 0) {
        if (errno == EINTR) {
            kill(pid, SIGKILL);
            waitpid(pid, NULL, 0);
            if (verbose) printf("Bad function: timed out after %u seconds\n", timeout);
            return 0;
        }
        return -1;
    }
    if (WIFEXITED(status)) {
        int code = WEXITSTATUS(status);
        if (code == 0) {
            if (verbose) printf("Nice function!\n");
            return 1;
        }
        if (verbose) printf("Bad function: exited with code %d\n", code);
        return 0;
    }
    if (WIFSIGNALED(status)) {
        int sig = WTERMSIG(status);
        if (sig == SIGALRM) {
            if (verbose) printf("Bad function: timed out after %u seconds\n", timeout);
        } else {
            if (verbose) printf("Bad function: %s\n", strsignal(sig));
        }
        return 0;
    }
    return -1;
}
