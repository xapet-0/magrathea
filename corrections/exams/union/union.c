/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   union.c                                            :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: marvin <marvin@42.fr>                      +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/26 10:00:00 by marvin            #+#    #+#             */
/*   Updated: 2026/10/26 10:00:00 by marvin           ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static int	in_prefix(char c, char *s, int len)
{
	int	i;

	i = 0;
	while (i < len)
	{
		if (s[i] == c)
			return (1);
		i++;
	}
	return (0);
}

int	main(int argc, char **argv)
{
	int	i;
	int	j;

	if (argc == 3)
	{
		i = 0;
		while (argv[1][i])
		{
			if (!in_prefix(argv[1][i], argv[1], i))
				write(1, &argv[1][i], 1);
			i++;
		}
		j = 0;
		while (argv[2][j])
		{
			if (!in_prefix(argv[2][j], argv[1], i) && !in_prefix(argv[2][j], argv[2], j))
				write(1, &argv[2][j], 1);
			j++;
		}
	}
	write(1, "\n", 1);
	return (0);
}
