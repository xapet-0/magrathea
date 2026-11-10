#include <unistd.h>

int main(int ac, char **av)
{
    if (ac < 2) {
        write(1, "\n", 1);
        return 0;
    }
    for (int i = 1; i < ac; i++) {
        char *s = av[i];
        int len = 0;
        while (s[len]) len++;
        if (len > 0) {
            write(1, &s[0], 1);
            write(1, &s[len - 1], 1);
        }
        write(1, "\n", 1);
    }
    return 0;
}
