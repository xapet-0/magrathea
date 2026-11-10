#include <unistd.h>

static int	reduce_sum(int n)
{
	int	s;

	while (n >= 10)
	{
		s = 0;
		while (n > 0)
		{
			s += n % 10;
			n /= 10;
		}
		n = s;
	}
	return (n);
}

int	main(int ac, char **av)
{
	int		i;
	int		sum;
	char	c;

	if (ac == 2)
	{
		i = 0;
		sum = 0;
		while (av[1][i])
		{
			if (av[1][i] >= '0' && av[1][i] <= '9')
				sum += av[1][i] - '0';
			i++;
		}
		c = reduce_sum(sum) + '0';
		write(1, &c, 1);
	}
	write(1, "\n", 1);
	return (0);
}
