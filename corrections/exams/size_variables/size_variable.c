#include <unistd.h>

static int scmp(const char *a, const char *b)
{
    while (*a && *a == *b) { a++; b++; }
    return (unsigned char)*a - (unsigned char)*b;
}

int main(int ac, char **av)
{
    if (ac == 2) {
        if (scmp(av[1], "int") == 0) write(1, "4 bytes", 7);
        else if (scmp(av[1], "char") == 0) write(1, "1 bytes", 7);
        else if (scmp(av[1], "float") == 0) write(1, "4 bytes", 7);
        else if (scmp(av[1], "double") == 0) write(1, "8 bytes", 7);
    }
    write(1, "\n", 1);
    return 0;
}
