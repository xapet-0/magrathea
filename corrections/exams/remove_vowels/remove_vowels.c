#include <unistd.h>

static int is_v(char c)
{
    if (c >= 'A' && c <= 'Z') c += 32;
    return (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u');
}

int main(int ac, char **av)
{
    if (ac == 2) {
        for (int i = 0; av[1][i]; i++)
            if (!is_v(av[1][i])) write(1, &av[1][i], 1);
    }
    write(1, "\n", 1);
    return 0;
}
