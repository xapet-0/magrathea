#include <unistd.h>

static void	put_char_case(char c, int upper)
{
	if (upper && c >= 'a' && c <= 'z')
		c -= 32;
	else if (!upper && c >= 'A' && c <= 'Z')
		c += 32;
	write(1, &c, 1);
}

int	main(int ac, char **av)
{
	int	i;
	int	w;
	int	in_w;

	if (ac == 2)
	{
		i = 0;
		w = 0;
		in_w = 0;
		while (av[1][i])
		{
			if (av[1][i] == ' ' || av[1][i] == '\t')
			{
				in_w = 0;
				write(1, &av[1][i], 1);
			}
			else
			{
				if (!in_w)
				{
					in_w = 1;
					w++;
				}
				put_char_case(av[1][i], (w % 2 == 0));
			}
			i++;
		}
	}
	write(1, "\n", 1);
	return (0);
}
