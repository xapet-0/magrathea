#include <unistd.h>

static int is_sp(char c) { return (c == ' ' || c == '\t'); }

static int w_cmp(char *a, int la, char *b, int lb)
{
    int i = 0;
    while (i < la && i < lb && a[i] == b[i])
        i++;
    if (i == la && i == lb) return (0);
    if (i == la) return (-1);
    if (i == lb) return (1);
    return ((unsigned char)a[i] - (unsigned char)b[i]);
}

int main(int argc, char **argv)
{
    char *w[1024];
    int wl[1024];
    int n = 0, i = 0, j;

    if (argc == 2)
    {
        char *s = argv[1];
        while (s[i])
        {
            while (s[i] && is_sp(s[i])) i++;
            if (!s[i]) break;
            w[n] = s + i;
            wl[n] = 0;
            while (s[i] && !is_sp(s[i])) { i++; wl[n]++; }
            n++;
        }
        for (i = 0; i < n; i++)
            for (j = i + 1; j < n; j++)
                if (w_cmp(w[i], wl[i], w[j], wl[j]) > 0)
                {
                    char *tw = w[i]; w[i] = w[j]; w[j] = tw;
                    int tl = wl[i]; wl[i] = wl[j]; wl[j] = tl;
                }
        for (i = 0; i < n; i++)
        {
            write(1, w[i], wl[i]);
            if (i + 1 < n) write(1, " ", 1);
        }
    }
    write(1, "\n", 1);
    return (0);
}
