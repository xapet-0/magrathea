#include <unistd.h>

static int	ft_atoi_p(char *s)
{
	int	i;
	int	res;

	i = 0;
	res = 0;
	while (s[i] >= '0' && s[i] <= '9')
	{
		res = res * 10 + (s[i] - '0');
		i++;
	}
	return (res);
}

int	main(int ac, char **av)
{
	int	i;
	int	n;

	if (ac == 3)
	{
		n = ft_atoi_p(av[2]);
		i = 1;
		while (av[1][i] && i < n)
		{
			write(1, &av[1][i], 1);
			i++;
		}
	}
	write(1, "\n", 1);
	return (0);
}
