#include <unistd.h>
#include <stdlib.h>
#include <string.h>

int main(int ac, char **av)
{
    if (ac != 2 || av[1][0] == '\0') return 1;
    char *pat = av[1];
    size_t plen = strlen(pat);
    size_t cap = 4096, len = 0;
    char *buf = malloc(cap);
    if (!buf) return 1;
    ssize_t r;
    while ((r = read(0, buf + len, cap - len)) > 0) {
        len += r;
        if (len == cap) {
            cap *= 2;
            buf = realloc(buf, cap);
            if (!buf) return 1;
        }
    }
    size_t i = 0;
    while (i < len) {
        int m = (i + plen <= len);
        for (size_t j = 0; m && j < plen; j++)
            if (buf[i + j] != pat[j]) m = 0;
        if (m) {
            for (size_t j = 0; j < plen; j++) write(1, "*", 1);
            i += plen;
        } else {
            write(1, &buf[i], 1);
            i++;
        }
    }
    free(buf);
    return 0;
}
