#include <unistd.h>
#include <stdlib.h>

static int slen(const char *s) { int i = 0; while (s[i]) i++; return i; }

static int cmp_abs(const char *a, const char *b)
{
    int la = slen(a), lb = slen(b);
    if (la != lb) return la - lb;
    for (int i = 0; i < la; i++) if (a[i] != b[i]) return a[i] - b[i];
    return 0;
}

int main(int ac, char **av)
{
    if (ac != 3) return 0;
    const char *a = av[1], *b = av[2];
    int sa = 1, sb = 1;
    if (*a == '-') { sa = -1; a++; }
    if (*b == '-') { sb = -1; b++; }
    while (a[0] == '0' && a[1]) a++;
    while (b[0] == '0' && b[1]) b++;
    int la = slen(a), lb = slen(b);
    char *res = malloc((la > lb ? la : lb) + 4);
    int k = 0, sign = 1;
    if (sa == sb) {
        sign = sa;
        int i = la - 1, j = lb - 1, c = 0;
        while (i >= 0 || j >= 0 || c) {
            int s = c + (i >= 0 ? a[i--] - '0' : 0) + (j >= 0 ? b[j--] - '0' : 0);
            res[k++] = '0' + (s % 10);
            c = s / 10;
        }
    } else {
        int c = cmp_abs(a, b);
        if (c == 0) { write(1, "0\n", 2); free(res); return 0; }
        if (c < 0) { const char *t = a; a = b; b = t; int tl = la; la = lb; lb = tl; sign = sb; }
        else sign = sa;
        int i = la - 1, j = lb - 1, borrow = 0;
        while (i >= 0) {
            int d = (a[i--] - '0') - (j >= 0 ? b[j--] - '0' : 0) - borrow;
            if (d < 0) { d += 10; borrow = 1; } else borrow = 0;
            res[k++] = '0' + d;
        }
    }
    while (k > 1 && res[k - 1] == '0') k--;
    if (sign < 0 && !(k == 1 && res[0] == '0')) write(1, "-", 1);
    while (k > 0) write(1, &res[--k], 1);
    write(1, "\n", 1);
    free(res);
    return 0;
}
