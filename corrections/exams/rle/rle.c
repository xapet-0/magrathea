#include <unistd.h>

static void	put_nbr(int n)
{
	char	c;

	if (n >= 10)
		put_nbr(n / 10);
	c = (n % 10) + '0';
	write(1, &c, 1);
}

int	main(int ac, char **av)
{
	int	i;
	int	cnt;

	if (ac == 2)
	{
		i = 0;
		while (av[1][i])
		{
			cnt = 1;
			while (av[1][i + cnt] == av[1][i])
				cnt++;
			if (cnt > 1)
				put_nbr(cnt);
			write(1, &av[1][i], 1);
			i += cnt;
		}
	}
	write(1, "\n", 1);
	return (0);
}
