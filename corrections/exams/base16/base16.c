#include <unistd.h>

static void puthex(unsigned long n)
{
    const char *h = "0123456789abcdef";
    if (n >= 16) puthex(n / 16);
    write(1, &h[n % 16], 1);
}

int main(int ac, char **av)
{
    if (ac == 2 && av[1][0] != '-') {
        unsigned long n = 0;
        int ok = (av[1][0] != '\0');
        for (int i = 0; av[1][i]; i++) {
            if (av[1][i] < '0' || av[1][i] > '9') { ok = 0; break; }
            n = n * 10 + (av[1][i] - '0');
        }
        if (ok) puthex(n);
    }
    write(1, "\n", 1);
    return 0;
}
