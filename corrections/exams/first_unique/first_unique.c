#include <unistd.h>

int	main(int ac, char **av)
{
	int	freq[256];
	int	i;

	if (ac == 2)
	{
		i = 0;
		while (i < 256)
			freq[i++] = 0;
		i = 0;
		while (av[1][i])
		{
			freq[(unsigned char)av[1][i]]++;
			i++;
		}
		i = 0;
		while (av[1][i])
		{
			if (freq[(unsigned char)av[1][i]] == 1)
			{
				write(1, &av[1][i], 1);
				break ;
			}
			i++;
		}
	}
	write(1, "\n", 1);
	return (0);
}
