#include <unistd.h>
#include <stdlib.h>

int main(int ac, char **av)
{
    if (ac == 3) {
        int n = atoi(av[2]);
        if (n > 0) {
            for (int i = 0; av[1][i]; i++) {
                if ((i + 1) % n != 0)
                    write(1, &av[1][i], 1);
            }
        }
    }
    write(1, "\n", 1);
    return 0;
}
