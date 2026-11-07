#include <unistd.h>

int main(int ac, char **av)
{
    if (ac == 2) {
        char *s = av[1];
        int i = 0;
        while (s[i]) {
            int cnt = 0;
            while (s[i] >= '0' && s[i] <= '9')
                cnt = cnt * 10 + (s[i++] - '0');
            if (cnt == 0) cnt = 1;
            if (s[i]) {
                for (int k = 0; k < cnt; k++)
                    write(1, &s[i], 1);
                i++;
            }
        }
    }
    write(1, "\n", 1);
    return 0;
}
