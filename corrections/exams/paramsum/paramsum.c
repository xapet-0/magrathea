/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   paramsum.c                                         :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: exam <marvin@42.fr>                        +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/08/01 13:04:24 by exam              #+#    #+#             */
/*   Updated: 2018/08/01 13:16:26 by exam             ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

void	print_nbr(int n)
{
	if (n >= 10)
		print_nbr(n /10);
	n = (n % 10) + '0';
	write(1, &n, 1);
}

int main (int argc, char **argv)
{
	int index = 1;
	if (argc == 1)
		write(1, "0", 1);
	else 
	{
		while (argv[index])
			index++;
		print_nbr(index - 1);
	}
	write(1, "\n", 1);	
	return (0);
}
