#include <unistd.h>

static int	ft_atoi_s(char *s)
{
	int	i;
	int	sign;
	int	res;

	i = 0;
	sign = 1;
	res = 0;
	if (s[i] == '-' || s[i] == '+')
	{
		if (s[i] == '-')
			sign = -1;
		i++;
	}
	while (s[i] >= '0' && s[i] <= '9')
	{
		res = res * 10 + (s[i] - '0');
		i++;
	}
	return (res * sign);
}

int	main(int ac, char **av)
{
	int	n;
	int	i;

	if (ac == 2)
	{
		n = ft_atoi_s(av[1]);
		if (n % 15 == 0)
			write(1, "ping pong", 9);
		else if (n % 3 == 0)
			write(1, "ping", 4);
		else if (n % 5 == 0)
			write(1, "pong", 4);
		else
		{
			i = 0;
			while (av[1][i])
			{
				write(1, &av[1][i], 1);
				i++;
			}
		}
	}
	write(1, "\n", 1);
	return (0);
}
