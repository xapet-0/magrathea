#include <unistd.h>
#include <stdlib.h>

static void gen(char *s, int n, char *cur, int *used, int d)
{
    if (d == n) {
        write(1, cur, n);
        write(1, "\n", 1);
        return;
    }
    for (int i = 0; i < n; i++) {
        if (!used[i]) {
            used[i] = 1;
            cur[d] = s[i];
            gen(s, n, cur, used, d + 1);
            used[i] = 0;
        }
    }
}

int main(int ac, char **av)
{
    if (ac != 2) { write(1, "\n", 1); return 0; }
    char *s = av[1];
    int n = 0;
    while (s[n]) n++;
    for (int i = 0; i < n; i++)
        for (int j = i + 1; j < n; j++)
            if (s[i] > s[j]) { char t = s[i]; s[i] = s[j]; s[j] = t; }
    char *cur = malloc(n + 1);
    int *used = calloc(n, sizeof(int));
    gen(s, n, cur, used, 0);
    free(cur);
    free(used);
    return 0;
}
