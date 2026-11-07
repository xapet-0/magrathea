#include <unistd.h>

static void putnbr(int n)
{
    if (n >= 10) putnbr(n / 10);
    char c = '0' + (n % 10);
    write(1, &c, 1);
}

int main(int ac, char **av)
{
    if (ac == 2 && av[1][0] != '\0' && av[1][1] == '\0')
        putnbr((unsigned char)av[1][0]);
    write(1, "\n", 1);
    return 0;
}
