#include <unistd.h>
int main(int ac, char **av)
{
	if (ac == 2)
	{
		int i = 0;
		while (av[1][i])
		{
			char c = av[1][i];
			if (c >= 'A' && c <= 'Z') c += 32;
			if ((c >= 'a' && c <= 'z') && (i == 0 || av[1][i - 1] == ' ' || av[1][i - 1] == '\t')) c -= 32;
			write(1, &c, 1);
			i++;
		}
	}
	write(1, "\n", 1);
	return (0);
}
