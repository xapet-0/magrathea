/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   rev_wstr.c                                         :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: marvin <marvin@42.fr>                      +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/26 10:00:00 by marvin            #+#    #+#             */
/*   Updated: 2026/10/26 10:00:00 by marvin           ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static int	is_sep(char c)
{
	return (c == ' ' || c == '\t' || c == '\0');
}

int	main(int argc, char **argv)
{
	int	i;
	int	start;
	int	end;
	int	first;

	if (argc == 2)
	{
		i = 0;
		while (argv[1][i])
			i++;
		first = 1;
		while (i >= 0)
		{
			while (i >= 0 && is_sep(argv[1][i]))
				i--;
			if (i < 0)
				break ;
			end = i;
			while (i >= 0 && !is_sep(argv[1][i]))
				i--;
			start = i + 1;
			if (!first)
				write(1, " ", 1);
			write(1, &argv[1][start], end - start + 1);
			first = 0;
		}
	}
	write(1, "\n", 1);
	return (0);
}
