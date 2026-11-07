#include <unistd.h>

static void	ft_putnbr(int n)
{
	long	nb;
	char	c;

	nb = n;
	if (nb < 0)
	{
		write(1, "-", 1);
		nb = -nb;
	}
	if (nb >= 10)
		ft_putnbr(nb / 10);
	c = (nb % 10) + '0';
	write(1, &c, 1);
}

void	ft_searchinsert(int *arr, int n, int target)
{
	int	i;

	i = 0;
	while (i < n && arr[i] < target)
		i++;
	ft_putnbr(i);
}
