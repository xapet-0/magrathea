#include <unistd.h>

void ft_sum_digits(int nbr)
{
    long n = nbr;
    if (n < 0) n = -n;
    while (n >= 10) {
        long s = 0;
        while (n > 0) { s += n % 10; n /= 10; }
        n = s;
    }
    char c = '0' + n;
    write(1, &c, 1);
    write(1, "\n", 1);
}
