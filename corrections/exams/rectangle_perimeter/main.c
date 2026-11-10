#include <stdio.h>
#include <stdlib.h>
int rectangle_perimeter(int l, int b);
int main(int ac, char **av){ if(ac!=3||!av[1][0]||!av[2][0]){printf("\n");return 0;} printf("%d\n", rectangle_perimeter(atoi(av[1]), atoi(av[2]))); return 0; }
