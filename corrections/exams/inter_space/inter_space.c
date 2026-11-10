#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 3) {
        int seen[256] = {0}, in2[256] = {0}, first = 1;
        for (int i = 0; av[2][i]; i++) in2[(unsigned char)av[2][i]] = 1;
        for (int i = 0; av[1][i]; i++) {
            unsigned char c = (unsigned char)av[1][i];
            if (in2[c] && !seen[c]) {
                seen[c] = 1;
                if (!first) write(1, " ", 1);
                first = 0;
                write(1, &av[1][i], 1);
            }
        }
    }
    write(1, "\n", 1);
    return 0;
}
