#include <unistd.h>
int main(int ac, char **av)
{
	if (ac == 3)
	{
		int seen[256] = {0}, in2[256] = {0}, i = 0;
		while (av[2][i]) in2[(unsigned char)av[2][i++]] = 1;
		i = 0;
		while (av[1][i])
		{
			unsigned char c = (unsigned char)av[1][i++];
			if (in2[c] && !seen[c]) { seen[c] = 1; write(1, &c, 1); }
		}
	}
	write(1, "\n", 1);
	return (0);
}
