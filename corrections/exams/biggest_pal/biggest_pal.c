/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   biggest_pal.c                                      :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: 1337 <marvin@42.fr>                        +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by 1337              #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by 1337             ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static void	expand(const char *s, int n, int l, int r, int *best_start, int *best_len)
{
	while (l >= 0 && r < n && s[l] == s[r])
	{
		if (r - l + 1 >= *best_len)
		{
			*best_len = r - l + 1;
			*best_start = l;
		}
		l--;
		r++;
	}
}

int	main(int argc, char **argv)
{
	int	n;
	int	i;
	int	best_start;
	int	best_len;

	if (argc == 2)
	{
		n = 0;
		while (argv[1][n])
			n++;
		best_start = 0;
		best_len = 0;
		i = 0;
		while (i < n)
		{
			expand(argv[1], n, i, i, &best_start, &best_len);
			expand(argv[1], n, i, i + 1, &best_start, &best_len);
			i++;
		}
		if (best_len > 0)
			write(1, argv[1] + best_start, best_len);
	}
	write(1, "\n", 1);
	return (0);
}
