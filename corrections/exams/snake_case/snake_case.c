#include <unistd.h>

int	main(int ac, char **av)
{
	int		i;
	int		cap;
	char	c;

	if (ac == 2)
	{
		i = 0;
		cap = 1;
		while (av[1][i])
		{
			c = av[1][i];
			if (c == '_')
				cap = 1;
			else
			{
				if (cap && c >= 'a' && c <= 'z')
					c -= 32;
				else if (!cap && c >= 'A' && c <= 'Z')
					c += 32;
				write(1, &c, 1);
				cap = 0;
			}
			i++;
		}
	}
	write(1, "\n", 1);
	return (0);
}
