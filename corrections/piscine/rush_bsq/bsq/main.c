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

#include "bsq.h"

static char	*read_all(int fd)
{
	char	*buf;
	int		len;
	int		r;

	buf = (char *)malloc(65536);
	if (!buf)
		return (NULL);
	len = 0;
	r = read(fd, buf + len, 4096);
	while (r > 0 && len + r < 65535)
	{
		len += r;
		r = read(fd, buf + len, 4096);
	}
	buf[len] = '\0';
	return (buf);
}

static int	parse_header(char *buf, t_map *m, int *hdr_end)
{
	int	i;
	int	l;

	l = 0;
	while (buf[l] && buf[l] != '\n')
		l++;
	if (l < 4)
		return (0);
	m->empty = buf[l - 3];
	m->oider = buf[l - 2];
	m->full = buf[l - 1];
	m->rows = 0;
	i = 0;
	while (i < l - 3)
	{
		if (buf[i] < '0' || buf[i] > '9')
			return (0);
		m->rows = m->rows * 10 + (buf[i++] - '0');
	}
	*hdr_end = l + 1;
	return (m->rows > 0);
}

static void	process_fd(int fd)
{
	char	*buf;
	t_map	m;
	int		hdr;
	int		c;

	buf = read_all(fd);
	if (!buf || !parse_header(buf, &m, &hdr))
	{
		write(2, "map error\n", 10);
		free(buf);
		return ;
	}
	m.grid = buf + hdr;
	c = 0;
	while (m.grid[c] && m.grid[c] != '\n')
		c++;
	m.cols = c;
	solve_and_print(&m);
	free(buf);
}

int	main(int argc, char **argv)
{
	int	i;
	int	fd;

	if (argc == 1)
		process_fd(0);
	i = 1;
	while (i < argc)
	{
		fd = open(argv[i], O_RDONLY);
		if (fd < 0)
			write(2, "map error\n", 10);
		else
		{
			process_fd(fd);
			close(fd);
		}
		i++;
	}
	return (0);
}
