/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   sastantua.c                                        :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static void	put_n(char c, int n)
{
	while (n-- > 0)
		write(1, &c, 1);
}

static int	base_width(int size)
{
	int	f;
	int	w;
	int	l;

	f = 1;
	w = 1;
	while (f <= size)
	{
		l = 2 + f;
		w += 2 * (l - 1);
		if (f < size)
			w += 2 * (2 + (f - 1) / 2);
		f++;
	}
	return (w);
}

static void	draw_line(int sp, int stars, int door, int knob)
{
	put_n(' ', sp);
	put_n('/', 1);
	if (door > 0)
	{
		put_n('*', (stars - door) / 2);
		if (knob && door >= 5)
		{
			put_n('|', door - 2);
			put_n('$', 1);
			put_n('|', 1);
		}
		else
			put_n('|', door);
		put_n('*', (stars - door) / 2);
	}
	else
		put_n('*', stars);
	put_n('\\', 1);
	put_n('\n', 1);
}

static void	draw_floor(int f, int size, int *w, int bw)
{
	int	r;
	int	d;

	r = 0;
	d = size - (1 - size % 2);
	while (r < f + 2)
	{
		if (f == size && r >= (f + 2) - d)
			draw_line((bw - *w) / 2, *w, d, r == (f + 2) - d / 2 - 1);
		else
			draw_line((bw - *w) / 2, *w, 0, 0);
		*w += 2;
		r++;
	}
}

void	sastantua(int size)
{
	int	f;
	int	w;
	int	bw;

	if (size <= 0)
		return ;
	bw = base_width(size);
	f = 1;
	w = 1;
	while (f <= size)
	{
		draw_floor(f, size, &w, bw);
		w += 2 * (1 + (f - 1) / 2);
		f++;
	}
}
