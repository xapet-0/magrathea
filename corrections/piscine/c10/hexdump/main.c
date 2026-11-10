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

#include <fcntl.h>
#include <unistd.h>

static void	put_hex(unsigned long v, int digits)
{
	char	*b;

	b = "0123456789abcdef";
	if (digits > 1)
		put_hex(v / 16, digits - 1);
	write(1, &b[v % 16], 1);
}

static void	dump_ascii(unsigned char *buf, int n)
{
	int	i;

	write(1, " |", 2);
	i = 0;
	while (i < n)
	{
		if (buf[i] >= 32 && buf[i] <= 126)
			write(1, &buf[i], 1);
		else
			write(1, ".", 1);
		i++;
	}
	write(1, "|\n", 2);
}

static void	dump_line(unsigned char *buf, int n, int off)
{
	int	i;

	put_hex(off, 8);
	write(1, "  ", 2);
	i = 0;
	while (i < 16)
	{
		if (i < n)
			put_hex(buf[i], 2);
		else
			write(1, "  ", 2);
		write(1, " ", 1);
		if (i == 7)
			write(1, " ", 1);
		i++;
	}
	dump_ascii(buf, n);
}

static void	dump_fd(int fd)
{
	unsigned char	buf[16];
	int				r;
	int				off;

	off = 0;
	r = read(fd, buf, 16);
	while (r > 0)
	{
		dump_line(buf, r, off);
		off += r;
		r = read(fd, buf, 16);
	}
	if (off > 0)
	{
		put_hex(off, 8);
		write(1, "\n", 1);
	}
}

int	main(int argc, char **argv)
{
	int	fd;

	if (argc < 3)
		return (1);
	fd = open(argv[2], O_RDONLY);
	if (fd < 0)
	{
		write(2, "hexdump: error\n", 15);
		return (1);
	}
	dump_fd(fd);
	close(fd);
	return (0);
}
