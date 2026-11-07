#include <unistd.h>

int main(int ac, char **av)
{
    if (ac != 2 || av[1][0] == '\0' || av[1][1] != '\0')
    {
        write(1, "\n", 1);
        return 0;
    }
    char c = av[1][0];
    if (c == 'a')
        c = 'z';
    else if (c == 'A')
        c = 'Z';
    else
        c -= 1;
    write(1, &c, 1);
    write(1, "\n", 1);
    return 0;
}
