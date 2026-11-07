#include <unistd.h>

void write_string(char *str)
{
    if (!str) return;
    int i = 0;
    while (str[i]) i++;
    if (i > 0) write(1, str, i);
}
