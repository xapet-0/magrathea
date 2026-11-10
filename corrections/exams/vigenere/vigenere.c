#include <unistd.h>

static int	is_alpha(char c)
{
	return ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'));
}

static int	shift_of(char k)
{
	if (k >= 'a' && k <= 'z')
		return (k - 'a');
	if (k >= 'A' && k <= 'Z')
		return (k - 'A');
	return (0);
}

int	main(int ac, char **av)
{
	int	i = 0, k = 0, klen = 0;
	char	c;

	if (ac == 3)
	{
		while (av[2][klen])
			klen++;
		while (av[1][i])
		{
			c = av[1][i];
			if (is_alpha(c) && klen > 0)
			{
				if (c >= 'a' && c <= 'z')
					c = 'a' + (c - 'a' + shift_of(av[2][k % klen])) % 26;
				else
					c = 'A' + (c - 'A' + shift_of(av[2][k % klen])) % 26;
				k++;
			}
			write(1, &c, 1);
			i++;
		}
	}
	write(1, "\n", 1);
	return (0);
}
