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

int	is_valid_move(int g[4][4], int *clues, int pos, int val);

static void	print_grid(int g[4][4])
{
	int		r;
	int		c;
	char	ch;

	r = 0;
	while (r < 4)
	{
		c = 0;
		while (c < 4)
		{
			ch = '0' + g[r][c];
			write(1, &ch, 1);
			if (c < 3)
				write(1, " ", 1);
			c++;
		}
		write(1, "\n", 1);
		r++;
	}
}

static int	solve(int g[4][4], int *clues, int pos)
{
	int	v;

	if (pos == 16)
		return (1);
	v = 1;
	while (v <= 4)
	{
		if (is_valid_move(g, clues, pos, v))
		{
			if (solve(g, clues, pos + 1))
				return (1);
			g[pos / 4][pos % 4] = 0;
		}
		v++;
	}
	return (0);
}

static int	parse_clues(char *s, int *clues)
{
	int	i;

	i = 0;
	while (i < 16)
	{
		if (s[i * 2] < '1' || s[i * 2] > '4')
			return (0);
		clues[i] = s[i * 2] - '0';
		if (i < 15 && s[i * 2 + 1] != ' ')
			return (0);
		i++;
	}
	return (s[31] == '\0');
}

int	main(int argc, char **argv)
{
	int	clues[16];
	int	g[4][4];
	int	i;

	i = 0;
	while (i < 16)
	{
		g[i / 4][i % 4] = 0;
		i++;
	}
	if (argc != 2 || !parse_clues(argv[1], clues) || !solve(g, clues, 0))
		write(1, "Error\n", 6);
	else
		print_grid(g);
	return (0);
}
