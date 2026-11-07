#include <unistd.h>

static int slen(const char *s) { int i = 0; while (s[i]) i++; return i; }

static int has_sub(const char *hay, const char *sub, int l)
{
    for (int i = 0; hay[i]; i++) {
        int j = 0;
        while (j < l && hay[i + j] == sub[j]) j++;
        if (j == l) return 1;
    }
    return 0;
}

int main(int ac, char **av)
{
    if (ac >= 2) {
        char *s0 = av[1];
        int n = slen(s0);
        for (int len = n; len >= 1; len--) {
            for (int st = 0; st + len <= n; st++) {
                int ok = 1;
                for (int k = 2; k < ac; k++)
                    if (!has_sub(av[k], s0 + st, len)) { ok = 0; break; }
                if (ok) {
                    write(1, s0 + st, len);
                    write(1, "\n", 1);
                    return 0;
                }
            }
        }
    }
    write(1, "\n", 1);
    return 0;
}
