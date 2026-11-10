#include <stdlib.h>

static int slen(const char *s) { int i = 0; while (s && s[i]) i++; return i; }

char *add_binary(char *a, char *b)
{
    int i = slen(a) - 1, j = slen(b) - 1, carry = 0;
    int max_l = (i > j ? i : j) + 3;
    char *buf = malloc(max_l);
    if (!buf)
        return NULL;
    int k = 0;
    while (i >= 0 || j >= 0 || carry) {
        int s = carry;
        if (i >= 0) s += a[i--] - '0';
        if (j >= 0) s += b[j--] - '0';
        buf[k++] = (s % 2) + '0';
        carry = s / 2;
    }
    if (k == 0) buf[k++] = '0';
    for (int l = 0; l < k / 2; l++) {
        char t = buf[l]; buf[l] = buf[k - 1 - l]; buf[k - 1 - l] = t;
    }
    buf[k] = '\0';
    return buf;
}

char *addBinary(char *a, char *b) { return add_binary(a, b); }
