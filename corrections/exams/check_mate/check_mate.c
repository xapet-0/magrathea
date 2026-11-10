/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   check_mate.c                                       :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: 1337 <marvin@42.fr>                        +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by 1337              #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by 1337             ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static int	is_piece(char c)
{
	return (c == 'P' || c == 'B' || c == 'R' || c == 'Q' || c == 'K');
}

static int	ray_hits_king(char **b, int n, int r, int c, int dr, int dc)
{
	r += dr;
	c += dc;
	while (r >= 0 && r < n && c >= 0 && c < n)
	{
		if (b[r][c] == 'K')
			return (1);
		if (is_piece(b[r][c]))
			return (0);
		r += dr;
		c += dc;
	}
	return (0);
}

static int	piece_attacks_king(char **b, int n, int r, int c)
{
	char	p;

	p = b[r][c];
	if (p == 'P')
	{
		if (r - 1 >= 0 && c - 1 >= 0 && b[r - 1][c - 1] == 'K')
			return (1);
		if (r - 1 >= 0 && c + 1 < n && b[r - 1][c + 1] == 'K')
			return (1);
	}
	if (p == 'R' || p == 'Q')
	{
		if (ray_hits_king(b, n, r, c, -1, 0) || ray_hits_king(b, n, r, c, 1, 0)
			|| ray_hits_king(b, n, r, c, 0, -1) || ray_hits_king(b, n, r, c, 0, 1))
			return (1);
	}
	if (p == 'B' || p == 'Q')
	{
		if (ray_hits_king(b, n, r, c, -1, -1) || ray_hits_king(b, n, r, c, -1, 1)
			|| ray_hits_king(b, n, r, c, 1, -1) || ray_hits_king(b, n, r, c, 1, 1))
			return (1);
	}
	return (0);
}

int	main(int argc, char **argv)
{
	int		n;
	int		r;
	int		c;
	char	**b;

	if (argc <= 1)
	{
		write(1, "\n", 1);
		return (0);
	}
	n = argc - 1;
	b = argv + 1;
	r = 0;
	while (r < n)
	{
		c = 0;
		while (c < n && b[r][c])
		{
			if (piece_attacks_king(b, n, r, c))
			{
				write(1, "Success\n", 8);
				return (0);
			}
			c++;
		}
		r++;
	}
	write(1, "Fail\n", 5);
	return (0);
}
