/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   count_alpha.c                                      :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: 1337 <marvin@42.fr>                        +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by 1337              #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by 1337             ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <stdio.h>

static int	is_alpha(char c)
{
	return ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'));
}

static char	to_lower(char c)
{
	if (c >= 'A' && c <= 'Z')
		return (c + 32);
	return (c);
}

int	main(int argc, char **argv)
{
	int		counts[26];
	char	order[26];
	int		n_unique;
	int		i;
	char	c;

	if (argc == 2)
	{
		i = -1;
		while (++i < 26)
			counts[i] = 0;
		n_unique = 0;
		i = 0;
		while (argv[1][i])
		{
			if (is_alpha(argv[1][i]))
			{
				c = to_lower(argv[1][i]);
				if (counts[c - 'a'] == 0)
					order[n_unique++] = c;
				counts[c - 'a']++;
			}
			i++;
		}
		i = -1;
		while (++i < n_unique)
			printf("%s%d%c", i > 0 ? ", " : "", counts[order[i] - 'a'], order[i]);
	}
	printf("\n");
	return (0);
}
