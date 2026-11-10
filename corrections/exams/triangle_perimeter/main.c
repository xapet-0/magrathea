#include <stdio.h>
#include <stdlib.h>
int triangle_perimeter(int a, int b, int c);
int main(int ac, char **av){ if(ac!=4||!av[1][0]||!av[2][0]||!av[3][0]){printf("\n");return 0;} printf("%d\n", triangle_perimeter(atoi(av[1]), atoi(av[2]), atoi(av[3]))); return 0; }
