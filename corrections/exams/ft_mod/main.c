#include <stdio.h>
#include <stdlib.h>
int ft_mod(int a, int b);
int main(int ac, char **av){ if(ac!=3){printf("\n");return 1;} printf("%d\n", ft_mod(atoi(av[1]), atoi(av[2]))); return 0; }
