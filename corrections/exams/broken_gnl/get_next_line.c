#include "get_next_line.h"

char *get_next_line(int fd)
{
    if (fd < 0) return NULL;
    char *line = malloc(100000);
    if (!line) return NULL;
    int i = 0;
    char c;
    int r;
    while ((r = read(fd, &c, 1)) > 0) {
        line[i++] = c;
        if (c == '\n') break;
    }
    if (i == 0 || r < 0) {
        free(line);
        return NULL;
    }
    line[i] = '\0';
    return line;
}
