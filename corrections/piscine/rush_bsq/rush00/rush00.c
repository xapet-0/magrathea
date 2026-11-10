/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   rush00.c                                           :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

void	ft_putchar(char c);

static void	print_row(int x, char l, char m, char r)
{
	int	i;

	if (x <= 0)
		return ;
	ft_putchar(l);
	i = 1;
	while (i < x - 1)
	{
		ft_putchar(m);
		i++;
	}
	if (x > 1)
		ft_putchar(r);
	ft_putchar('\n');
}

void	rush(int x, int y)
{
	int	j;

	if (x <= 0 || y <= 0)
		return ;
	print_row(x, 'o', '-', 'o');
	j = 1;
	while (j < y - 1)
	{
		print_row(x, '|', ' ', '|');
		j++;
	}
	if (y > 1)
		print_row(x, 'o', '-', 'o');
}
