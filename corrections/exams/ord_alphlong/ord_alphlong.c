#include <unistd.h>
#include <stdlib.h>

static int is_ws(char c) { return c == ' ' || c == '\t'; }
static char low(char c) { return (c >= 'A' && c <= 'Z') ? c + 32 : c; }

static int wcmp(const char *a, int la, const char *b, int lb)
{
    if (la != lb) return la - lb;
    for (int i = 0; i < la; i++) {
        char ca = low(a[i]), cb = low(b[i]);
        if (ca != cb) return ca - cb;
    }
    return 0;
}

int main(int ac, char **av)
{
    if (ac == 2) {
        char *s = av[1];
        const char *w[2048];
        int wl[2048], n = 0, i = 0;
        while (s[i]) {
            while (s[i] && is_ws(s[i])) i++;
            if (s[i]) {
                int st = i;
                while (s[i] && !is_ws(s[i])) i++;
                w[n] = s + st;
                wl[n++] = i - st;
            }
        }
        for (int a = 0; a < n; a++) {
            for (int b = 0; b < n - 1 - a; b++) {
                if (wcmp(w[b], wl[b], w[b + 1], wl[b + 1]) > 0) {
                    const char *tw = w[b]; w[b] = w[b + 1]; w[b + 1] = tw;
                    int tl = wl[b]; wl[b] = wl[b + 1]; wl[b + 1] = tl;
                }
            }
        }
        for (int a = 0; a < n; a++) {
            if (a > 0) {
                if (wl[a] == wl[a - 1]) write(1, " ", 1);
                else write(1, "\n", 1);
            }
            write(1, w[a], wl[a]);
        }
    }
    write(1, "\n", 1);
    return 0;
}
