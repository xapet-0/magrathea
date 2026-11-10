#include <unistd.h>
#include <stdlib.h>

static int slen(const char *s) { int i = 0; while (s[i]) i++; return i; }

int main(int ac, char **av)
{
    if (ac != 3) return 0;
    const char *a = av[1], *b = av[2];
    int sign = 1;
    if (*a == '-') { sign = -sign; a++; }
    if (*b == '-') { sign = -sign; b++; }
    while (a[0] == '0' && a[1]) a++;
    while (b[0] == '0' && b[1]) b++;
    if (a[0] == '0' || b[0] == '0') { write(1, "0\n", 2); return 0; }
    int la = slen(a), lb = slen(b);
    int *res = malloc(sizeof(int) * (la + lb));
    for (int i = 0; i < la + lb; i++) res[i] = 0;
    for (int i = la - 1; i >= 0; i--) {
        for (int j = lb - 1; j >= 0; j--) {
            int p = (a[i] - '0') * (b[j] - '0') + res[i + j + 1];
            res[i + j + 1] = p % 10;
            res[i + j] += p / 10;
        }
    }
    if (sign < 0) write(1, "-", 1);
    int k = 0;
    while (k < la + lb - 1 && res[k] == 0) k++;
    while (k < la + lb) {
        char c = '0' + res[k++];
        write(1, &c, 1);
    }
    write(1, "\n", 1);
    free(res);
    return 0;
}
