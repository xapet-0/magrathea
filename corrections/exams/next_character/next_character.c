#include <unistd.h>
int main(int argc, char **argv) {
    if (argc != 2 || !argv[1][0]) {
        write(1, "\n", 1);
        return 0;
    }
    char c = argv[1][0];
    if (c == 'z')
        c = 'a';
    else if (c == 'Z')
        c = 'A';
    else
        c = c + 1;
    write(1, &c, 1);
    write(1, "\n", 1);
    return 0;
}
