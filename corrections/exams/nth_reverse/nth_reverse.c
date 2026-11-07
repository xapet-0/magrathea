#include <unistd.h>
#include <stdlib.h>

int main(int ac, char **av)
{
    if (ac == 3) {
        int n = atoi(av[2]);
        char *s = av[1];
        int len = 0;
        while (s[len]) len++;
        if (n > 0) {
            for (int i = 0; i < len; i += n) {
                int end = (i + n < len) ? (i + n - 1) : (len - 1);
                for (int j = end; j >= i; j--)
                    write(1, &s[j], 1);
            }
        }
    }
    write(1, "\n", 1);
    return 0;
}
