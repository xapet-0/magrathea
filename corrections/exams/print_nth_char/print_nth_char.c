#include <unistd.h>

void print_nth_char(char *str, int n)
{
    if (!str || n <= 0) {
        write(1, "\n", 1);
        return;
    }
    for (int i = 0; str[i]; i++) {
        if ((i + 1) % n == 0)
            write(1, &str[i], 1);
    }
    write(1, "\n", 1);
}
