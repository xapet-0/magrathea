#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 2) {
        int n = 0;
        while (av[1][n]) n++;
        int ok = 1;
        for (int i = 0; i < n / 2; i++)
            if (av[1][i] != av[1][n - 1 - i]) ok = 0;
        if (ok) write(1, av[1], n);
    }
    write(1, "\n", 1);
    return 0;
}
