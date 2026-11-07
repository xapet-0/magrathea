/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   print_memory.c                                     :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: marvin <marvin@42.fr>                      +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/26 10:00:00 by marvin            #+#    #+#             */
/*   Updated: 2026/10/26 10:00:00 by marvin           ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static void	put_hex_byte(unsigned char b)
{
	char	*hex;

	hex = "0123456789abcdef";
	write(1, &hex[b / 16], 1);
	write(1, &hex[b % 16], 1);
}

static void	print_line(const unsigned char *p, size_t rem)
{
	size_t	j;
	char	c;

	j = 0;
	while (j < 16)
	{
		if (j < rem)
			put_hex_byte(p[j]);
		else
			write(1, "  ", 2);
		if (j % 2 == 1)
			write(1, " ", 1);
		j++;
	}
	j = 0;
	while (j < 16 && j < rem)
	{
		c = (p[j] >= 32 && p[j] <= 126) ? (char)p[j] : '.';
		write(1, &c, 1);
		j++;
	}
	write(1, "\n", 1);
}

void	print_memory(const void *addr, size_t size)
{
	size_t				i;
	const unsigned char	*p;

	p = (const unsigned char *)addr;
	i = 0;
	while (i < size)
	{
		print_line(p + i, size - i);
		i += 16;
	}
}
