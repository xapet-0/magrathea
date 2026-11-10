#include <unistd.h>

int	main(int ac, char **av)
{
	int	i;
	int	len;
	int	best_s;
	int	best_l;

	if (ac == 2)
	{
		i = 0;
		best_s = 0;
		best_l = 0;
		while (av[1][i])
		{
			while (av[1][i] == ' ' || av[1][i] == '\t')
				i++;
			len = 0;
			while (av[1][i + len] && av[1][i + len] != ' ' && av[1][i + len] != '\t')
				len++;
			if (len > best_l)
			{
				best_l = len;
				best_s = i;
			}
			i += len;
		}
		if (best_l > 0)
			write(1, &av[1][best_s], best_l);
	}
	write(1, "\n", 1);
	return (0);
}
