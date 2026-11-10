#include <stdio.h>
#include <stdlib.h>
int ft_div(int a, int b);
int main(int ac, char **av){ if(ac!=3){printf("\n");return 1;} printf("%d\n", ft_div(atoi(av[1]), atoi(av[2]))); return 0; }
