#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 2) {
        int cap = 1;
        for (int i = 0; av[1][i]; i++) {
            char c = av[1][i];
            if (c == '_') { cap = 1; continue; }
            if (cap && c >= 'a' && c <= 'z') c -= 32;
            else if (!cap && c >= 'A' && c <= 'Z') c += 32;
            cap = 0;
            write(1, &c, 1);
        }
    }
    write(1, "\n", 1);
    return 0;
}
