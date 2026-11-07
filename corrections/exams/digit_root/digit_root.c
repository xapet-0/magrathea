#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 2 && av[1][0]) {
        long s = 0;
        for (int i = 0; av[1][i]; i++) {
            if (av[1][i] >= '0' && av[1][i] <= '9')
                s += av[1][i] - '0';
        }
        while (s >= 10) {
            long t = 0;
            while (s > 0) { t += s % 10; s /= 10; }
            s = t;
        }
        char c = '0' + s;
        write(1, &c, 1);
    }
    write(1, "\n", 1);
    return 0;
}
