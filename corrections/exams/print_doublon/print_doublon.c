#include <stdio.h>

void print_doublon(int *a, int na, int *b, int nb)
{
    int i = 0, j = 0, first = 1;
    while (i < na && j < nb) {
        if (a[i] == b[j]) {
            if (!first) printf(" ");
            printf("%d", a[i]);
            first = 0;
            i++; j++;
        } else if (a[i] < b[j]) i++;
        else j++;
    }
    printf("\n");
}
