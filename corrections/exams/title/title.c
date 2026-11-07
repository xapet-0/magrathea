#include <unistd.h>

static int is_ws(char c) { return c == ' ' || c == '\t'; }

int main(int ac, char **av)
{
    if (ac == 2) {
        for (int i = 0; av[1][i]; i++) {
            char c = av[1][i];
            if ((i == 0 || is_ws(av[1][i - 1])) && c >= 'a' && c <= 'z')
                c -= 32;
            write(1, &c, 1);
        }
    }
    write(1, "\n", 1);
    return 0;
}
