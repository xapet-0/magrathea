/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   main.c                                             :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static int	can_place(int g[9][9], int r, int c, int v)
{
	int	i;

	i = 0;
	while (i < 9)
	{
		if (g[r][i] == v || g[i][c] == v)
			return (0);
		if (g[(r / 3) * 3 + i / 3][(c / 3) * 3 + i % 3] == v)
			return (0);
		i++;
	}
	return (1);
}

static int	solve_sud(int g[9][9], int pos)
{
	int	r;
	int	c;
	int	v;

	if (pos == 81)
		return (1);
	r = pos / 9;
	c = pos % 9;
	if (g[r][c] != 0)
		return (solve_sud(g, pos + 1));
	v = 1;
	while (v <= 9)
	{
		if (can_place(g, r, c, v))
		{
			g[r][c] = v;
			if (solve_sud(g, pos + 1))
				return (1);
			g[r][c] = 0;
		}
		v++;
	}
	return (0);
}

static void	print_sud(int g[9][9])
{
	int		r;
	int		c;
	char	ch;

	r = 0;
	while (r < 9)
	{
		c = 0;
		while (c < 9)
		{
			ch = '0' + g[r][c];
			write(1, &ch, 1);
			if (c < 8)
				write(1, " ", 1);
			c++;
		}
		write(1, "\n", 1);
		r++;
	}
}

static int	load_sud(int argc, char **argv, int g[9][9])
{
	int	r;
	int	c;

	if (argc != 10)
		return (0);
	r = 0;
	while (r < 9)
	{
		c = 0;
		while (c < 9)
		{
			if (argv[r + 1][c] == '.')
				g[r][c] = 0;
			else if (argv[r + 1][c] >= '1' && argv[r + 1][c] <= '9')
				g[r][c] = argv[r + 1][c] - '0';
			else
				return (0);
			c++;
		}
		if (argv[r + 1][9] != '\0')
			return (0);
		r++;
	}
	return (1);
}

int	main(int argc, char **argv)
{
	int	g[9][9];

	if (!load_sud(argc, argv, g) || !solve_sud(g, 0))
		write(1, "Error\n", 6);
	else
		print_sud(g);
	return (0);
}
