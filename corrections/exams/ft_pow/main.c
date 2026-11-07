#include <stdio.h>
#include <stdlib.h>
int ft_pow(int nb, int power);
int main(int ac, char **av){ if(ac!=3){printf("\n");return 1;} printf("%d\n", ft_pow(atoi(av[1]), atoi(av[2]))); return 0; }
