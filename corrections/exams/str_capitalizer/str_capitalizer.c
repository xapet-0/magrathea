/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   str_capitalizer.c                                  :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: marvin <marvin@42.fr>                      +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/26 10:00:00 by marvin            #+#    #+#             */
/*   Updated: 2026/10/26 10:00:00 by marvin           ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static void	cap_str(char *s)
{
	int		i;
	char	c;

	i = 0;
	while (s[i])
	{
		c = s[i];
		if (c >= 'A' && c <= 'Z')
			c += 32;
		if ((c >= 'a' && c <= 'z') && (i == 0 || s[i - 1] == ' ' || s[i - 1] == '\t'))
			c -= 32;
		write(1, &c, 1);
		i++;
	}
}

int	main(int argc, char **argv)
{
	int	i;

	if (argc < 2)
		write(1, "\n", 1);
	else
	{
		i = 1;
		while (i < argc)
		{
			cap_str(argv[i]);
			write(1, "\n", 1);
			i++;
		}
	}
	return (0);
}
