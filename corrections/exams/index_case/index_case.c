#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 2) {
        for (int i = 0; av[1][i]; i++) {
            char c = av[1][i];
            if (i % 2 == 0 && c >= 'a' && c <= 'z') c -= 32;
            else if (i % 2 == 1 && c >= 'A' && c <= 'Z') c += 32;
            write(1, &c, 1);
        }
    }
    write(1, "\n", 1);
    return 0;
}
