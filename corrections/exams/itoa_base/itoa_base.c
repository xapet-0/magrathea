#include <stdlib.h>

char *itoa_base(int value, int base)
{
    if (base < 2 || base > 16)
        return NULL;
    long n = value;
    int neg = (n < 0 && base == 10);
    if (n < 0)
        n = -n;
    char buf[65];
    int i = 0;
    const char *digits = "0123456789ABCDEF";
    if (n == 0)
        buf[i++] = '0';
    while (n > 0)
    {
        buf[i++] = digits[n % base];
        n /= base;
    }
    if (neg)
        buf[i++] = '-';
    char *res = malloc(i + 1);
    if (!res)
        return NULL;
    for (int j = 0; j < i; j++)
        res[j] = buf[i - 1 - j];
    res[i] = '\0';
    return res;
}
