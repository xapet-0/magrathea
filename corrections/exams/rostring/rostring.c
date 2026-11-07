/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   rostring.c                                         :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: marvin <marvin@42.fr>                      +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/26 10:00:00 by marvin            #+#    #+#             */
/*   Updated: 2026/10/26 10:00:00 by marvin           ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static int	is_ws(char c)
{
	return (c == ' ' || c == '\t');
}

static void	rostring_run(char *s)
{
	int	i;
	int	f_start;
	int	f_end;
	int	printed;

	i = 0;
	while (is_ws(s[i]))
		i++;
	f_start = i;
	while (s[i] && !is_ws(s[i]))
		i++;
	f_end = i;
	printed = 0;
	while (s[i])
	{
		while (is_ws(s[i]))
			i++;
		if (!s[i])
			break ;
		if (printed)
			write(1, " ", 1);
		while (s[i] && !is_ws(s[i]))
			write(1, &s[i++], 1);
		printed = 1;
	}
	if (f_end > f_start)
	{
		if (printed)
			write(1, " ", 1);
		write(1, &s[f_start], f_end - f_start);
	}
}

int	main(int argc, char **argv)
{
	if (argc >= 2)
		rostring_run(argv[1]);
	write(1, "\n", 1);
	return (0);
}
