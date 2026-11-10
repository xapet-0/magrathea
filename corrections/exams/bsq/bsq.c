#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>

static int solve_stream(int fd)
{
    int cap = 65536, len = 0, r;
    char *buf = malloc(cap);
    if (!buf) return 0;
    while ((r = read(fd, buf + len, cap - len - 1)) > 0) {
        len += r;
        if (len + 1 >= cap) {
            cap *= 2;
            char *nb = malloc(cap);
            for (int i = 0; i < len; i++) nb[i] = buf[i];
            free(buf);
            buf = nb;
        }
    }
    buf[len] = '\0';
    int nl = 0;
    while (nl < len && buf[nl] != '\n') nl++;
    if (nl < 4 || nl >= len) { free(buf); return 0; }
    char full_c = buf[nl - 1], obs_c = buf[nl - 2], empty_c = buf[nl - 3];
    if (empty_c == obs_c || empty_c == full_c || obs_c == full_c) { free(buf); return 0; }
    if (empty_c < 32 || obs_c < 32 || full_c < 32) { free(buf); return 0; }
    int rows = 0;
    for (int i = 0; i < nl - 3; i++) {
        if (buf[i] < '0' || buf[i] > '9') { free(buf); return 0; }
        rows = rows * 10 + (buf[i] - '0');
    }
    if (rows <= 0) { free(buf); return 0; }
    char *grid = buf + nl + 1;
    int rem = len - (nl + 1);
    int cols = 0;
    while (cols < rem && grid[cols] != '\n') cols++;
    if (cols <= 0 || rem != rows * (cols + 1)) { free(buf); return 0; }
    for (int i = 0; i < rows; i++) {
        if (grid[i * (cols + 1) + cols] != '\n') { free(buf); return 0; }
        for (int j = 0; j < cols; j++) {
            char ch = grid[i * (cols + 1) + j];
            if (ch != empty_c && ch != obs_c) { free(buf); return 0; }
        }
    }
    int *dp = malloc(sizeof(int) * rows * cols);
    int best_sz = 0, best_r = 0, best_c = 0;
    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
            if (grid[i * (cols + 1) + j] == obs_c) dp[i * cols + j] = 0;
            else if (i == 0 || j == 0) dp[i * cols + j] = 1;
            else {
                int m = dp[(i - 1) * cols + j];
                if (dp[i * cols + (j - 1)] < m) m = dp[i * cols + (j - 1)];
                if (dp[(i - 1) * cols + (j - 1)] < m) m = dp[(i - 1) * cols + (j - 1)];
                dp[i * cols + j] = 1 + m;
            }
            if (dp[i * cols + j] > best_sz) {
                best_sz = dp[i * cols + j];
                best_r = i;
                best_c = j;
            }
        }
    }
    for (int i = best_r - best_sz + 1; i <= best_r; i++)
        for (int j = best_c - best_sz + 1; j <= best_c; j++)
            grid[i * (cols + 1) + j] = full_c;
    write(1, grid, rem);
    free(dp);
    free(buf);
    return 1;
}

int main(int ac, char **av)
{
    if (ac == 1) {
        if (!solve_stream(0)) write(2, "map error\n", 10);
        return 0;
    }
    for (int i = 1; i < ac; i++) {
        int fd = open(av[i], O_RDONLY);
        if (fd < 0 || !solve_stream(fd))
            write(2, "map error\n", 10);
        if (fd >= 0) close(fd);
        if (ac > 2 && i + 1 < ac) write(1, "\n", 1);
    }
    return 0;
}
