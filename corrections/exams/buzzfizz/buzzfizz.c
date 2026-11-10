#include <unistd.h>

static void putnbr(int n)
{
    if (n >= 10) putnbr(n / 10);
    char c = '0' + (n % 10);
    write(1, &c, 1);
}

int main(void)
{
    for (int i = 1; i <= 100; i++) {
        if (i % 28 == 0) write(1, "buzzfizz\n", 9);
        else if (i % 4 == 0) write(1, "buzz\n", 5);
        else if (i % 7 == 0) write(1, "fizz\n", 5);
        else { putnbr(i); write(1, "\n", 1); }
    }
    return 0;
}
