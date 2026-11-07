#include <unistd.h>

static int is_ws(char c) { return (c == ' ' || c == '\t' || c == '\n'); }

static void putnbr(int n)
{
    if (n >= 10) putnbr(n / 10);
    char c = '0' + (n % 10);
    write(1, &c, 1);
}

int main(int ac, char **av)
{
    if (ac == 2) {
        char *s = av[1];
        int i = 0, len = 0, first = 1;
        while (s[i]) {
            if (!is_ws(s[i])) len++;
            else if (len > 0) {
                if (!first) write(1, ", ", 2);
                putnbr(len);
                first = 0;
                len = 0;
            }
            i++;
        }
        if (len > 0) {
            if (!first) write(1, ", ", 2);
            putnbr(len);
        }
    }
    write(1, "\n", 1);
    return 0;
}
