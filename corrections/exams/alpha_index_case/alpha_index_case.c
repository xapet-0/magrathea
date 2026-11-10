#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 2) {
        for (int i = 0; av[1][i]; i++) {
            char c = av[1][i];
            if (c >= 'a' && c <= 'z') {
                int pos = c - 'a' + 1;
                if (pos % 2 == 0) c -= 32;
            } else if (c >= 'A' && c <= 'Z') {
                int pos = c - 'A' + 1;
                if (pos % 2 == 1) c += 32;
            }
            write(1, &c, 1);
        }
    }
    write(1, "\n", 1);
    return 0;
}
