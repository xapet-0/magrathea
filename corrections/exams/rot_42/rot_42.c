#include <unistd.h>
int main(int ac, char **av)
{
	if (ac == 2)
	{
		int i = 0;
		while (av[1][i])
		{
			char c = av[1][i++];
			if (c >= 'a' && c <= 'z') c = (c - 'a' + 42) % 26 + 'a';
			else if (c >= 'A' && c <= 'Z') c = (c - 'A' + 42) % 26 + 'A';
			write(1, &c, 1);
		}
	}
	write(1, "\n", 1);
	return (0);
}
