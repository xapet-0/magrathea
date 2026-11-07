#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 4) {
        int a = atoi(av[1]), b = atoi(av[3]);
        char op = av[2][0];
        if (op == '+') printf("%d\n", a + b);
        else if (op == '-') printf("%d\n", a - b);
        else if (op == '*') printf("%d\n", a * b);
        else if (op == '/') printf("%d\n", a / b);
        else if (op == '%') printf("%d\n", a % b);
        return 0;
    }
    write(1, "\n", 1);
    return 0;
}
