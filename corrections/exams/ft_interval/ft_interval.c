#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 2) {
        for (int i = 0; av[1][i]; i++) {
            char c = av[1][i];
            if (i > 0) {
                if (i % 3 == 0) c = '5';
                else if (i % 5 == 0) c = '3';
            }
            write(1, &c, 1);
        }
    }
    write(1, "\n", 1);
    return 0;
}
