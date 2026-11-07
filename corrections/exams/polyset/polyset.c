#include <stdio.h>

static int scmp(const char *a, const char *b)
{
    while (*a && *a == *b) { a++; b++; }
    return *a - *b;
}

int main(int ac, char **av)
{
    int first = 1;
    for (int i = 1; i < ac; i++) {
        int dup = 0;
        for (int j = 1; j < i; j++)
            if (scmp(av[i], av[j]) == 0) dup = 1;
        if (!dup) {
            if (!first) printf(" ");
            first = 0;
            printf("%s", av[i]);
        }
    }
    printf("\n");
    return 0;
}
