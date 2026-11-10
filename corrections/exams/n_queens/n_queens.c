#include <stdio.h>
#include <stdlib.h>

static int n;
static int cols[32];

static int ok_pos(int c, int r)
{
    for (int i = 0; i < c; i++) {
        int d = cols[i] - r;
        if (d < 0) d = -d;
        if (cols[i] == r || d == c - i) return 0;
    }
    return 1;
}

static void solve(int c)
{
    if (c == n) {
        for (int i = 0; i < n; i++)
            printf("%d%s", cols[i], (i + 1 == n) ? "\n" : " ");
        return;
    }
    for (int r = 0; r < n; r++) {
        if (ok_pos(c, r)) {
            cols[c] = r;
            solve(c + 1);
        }
    }
}

int main(int ac, char **av)
{
    if (ac != 2) return 0;
    n = atoi(av[1]);
    if (n <= 0) return 0;
    solve(0);
    return 0;
}
