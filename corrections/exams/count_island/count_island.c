/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   count_island.c                                     :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: 1337 <marvin@42.fr>                        +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by 1337              #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by 1337             ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <fcntl.h>
#include <stdlib.h>
#include <unistd.h>

static void	dfs(char *buf, int rows, int cols, int r, int c, char id)
{
	int	idx;

	if (r < 0 || r >= rows || c < 0 || c >= cols)
		return ;
	idx = r * (cols + 1) + c;
	if (buf[idx] != 'X')
		return ;
	buf[idx] = id;
	dfs(buf, rows, cols, r - 1, c, id);
	dfs(buf, rows, cols, r + 1, c, id);
	dfs(buf, rows, cols, r, c - 1, id);
	dfs(buf, rows, cols, r, c + 1, id);
}

static int	validate_grid(const char *buf, int len, int *rows, int *cols)
{
	int	i;
	int	cur_col;

	if (len <= 0)
		return (0);
	*cols = -1;
	*rows = 0;
	cur_col = 0;
	i = 0;
	while (i < len)
	{
		if (buf[i] == '\n')
		{
			if (cur_col == 0 || cur_col > 1024)
				return (0);
			if (*cols == -1)
				*cols = cur_col;
			else if (cur_col != *cols)
				return (0);
			(*rows)++;
			cur_col = 0;
		}
		else if (buf[i] == '.' || buf[i] == 'X')
			cur_col++;
		else
			return (0);
		i++;
	}
	return (cur_col == 0 && *rows > 0 && *cols > 0);
}

int	main(int argc, char **argv)
{
	int		fd;
	char	*buf;
	int		total;
	int		r;
	int		 rows;
	int		cols;
	char	id;

	if (argc != 2)
	{
		write(1, "\n", 1);
		return (0);
	}
	fd = open(argv[1], O_RDONLY);
	if (fd < 0)
	{
		write(1, "\n", 1);
		return (0);
	}
	buf = (char *)malloc(1048576);
	if (!buf)
	{
		close(fd);
		write(1, "\n", 1);
		return (0);
	}
	total = 0;
	while ((r = read(fd, buf + total, 65536)) > 0)
	{
		total += r;
		if (total >= 1048570)
			break ;
	}
	close(fd);
	if (r < 0 || !validate_grid(buf, total, &rows, &cols))
	{
		free(buf);
		write(1, "\n", 1);
		return (0);
	}
	id = '0';
	r = 0;
	while (r < rows)
	{
		total = 0;
		while (total < cols)
		{
			if (buf[r * (cols + 1) + total] == 'X')
			{
				dfs(buf, rows, cols, r, total, id);
				id++;
			}
			total++;
		}
		r++;
	}
	write(1, buf, rows * (cols + 1));
	free(buf);
	return (0);
}
