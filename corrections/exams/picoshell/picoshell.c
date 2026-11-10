#include <unistd.h>
#include <sys/wait.h>
#include <stdlib.h>

int picoshell(char **cmds[])
{
    int in_fd = -1;
    int fd[2];
    int i = 0;
    while (cmds && cmds[i]) {
        int has_next = (cmds[i + 1] != NULL);
        if (has_next && pipe(fd) < 0) return 1;
        pid_t pid = fork();
        if (pid < 0) return 1;
        if (pid == 0) {
            if (in_fd != -1) { dup2(in_fd, 0); close(in_fd); }
            if (has_next) { close(fd[0]); dup2(fd[1], 1); close(fd[1]); }
            execvp(cmds[i][0], cmds[i]);
            exit(1);
        }
        if (in_fd != -1) close(in_fd);
        if (has_next) { close(fd[1]); in_fd = fd[0]; }
        i++;
    }
    while (wait(NULL) > 0);
    return 0;
}
