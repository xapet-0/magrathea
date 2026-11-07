#include <unistd.h>

int	main(int ac, char **av)
{
	int	len;

	if (ac == 2 && av[1][0] != '\0')
	{
		len = 0;
		while (av[1][len])
			len++;
		write(1, &av[1][0], 1);
		write(1, &av[1][len - 1], 1);
	}
	write(1, "\n", 1);
	return (0);
}
