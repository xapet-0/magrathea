/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   tab_mult.c                                         :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: cletinic <marvin@42.fr>                    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/07/03 15:20:34 by cletinic          #+#    #+#             */
/*   Updated: 2018/07/03 16:29:52 by cletinic         ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>
#include <stdio.h>

void printnbr(int n)
{
	if (n >= 10)
		printnbr (n / 10);
	n = (n % 10) + '0';
	write(1, &n, 1);
}

int ft_atoi(char *s)
{
	int index;
	int ret;
	
	index = 0;
	ret = 0;
	while ((s[index]) && (s[index] >= '0' && s[index] <= '9'))
		ret = s[index++] - '0' + (ret * 10);
	return (ret);
}

int main (int argc, char **argv)
{
	int index;
	int base;

	index = 1;
	if (argc > 1)
	{
		base = ft_atoi(argv[1]);
		while (index <= 9)
		{
			printnbr(index);
			write(1, " x ", 3);
			printnbr(base);
			write(1, " = ", 3);
			printnbr(index * base);
			write(1, "\n", 1);
			index++;		
		}
	}
	else
		write(1, "\n", 1);
	return (0);
}
