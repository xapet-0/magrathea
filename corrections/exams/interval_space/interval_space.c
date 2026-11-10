#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 2) {
        for (int i = 0; av[1][i]; i++) {
            if (i > 0) write(1, "   ", 3);
            write(1, &av[1][i], 1);
        }
    }
    write(1, "\n", 1);
    return 0;
}
