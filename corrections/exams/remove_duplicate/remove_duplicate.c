#include <unistd.h>

int main(int argc, char **argv)
{
    int seen[256] = {0};
    int i = 0;

    if (argc == 2)
    {
        while (argv[1][i])
        {
            unsigned char c = (unsigned char)argv[1][i];
            if (!seen[c])
            {
                seen[c] = 1;
                write(1, &c, 1);
            }
            i++;
        }
    }
    write(1, "\n", 1);
    return (0);
}
