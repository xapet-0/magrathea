#include <unistd.h>
int main(int ac, char **av)
{
	if (ac == 2)
	{
		int i = 0;
		while (av[1][i])
		{
			char c = av[1][i++];
			if (c >= 'a' && c <= 'z') c -= 32;
			else if (c >= 'A' && c <= 'Z') c += 32;
			write(1, &c, 1);
		}
	}
	write(1, "\n", 1);
	return (0);
}
