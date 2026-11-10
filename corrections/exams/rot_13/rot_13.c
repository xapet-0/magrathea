/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   rot_13.c                                           :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: cletinic <marvin@42.fr>                    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/07/02 15:42:31 by cletinic          #+#    #+#             */
/*   Updated: 2018/07/02 15:43:31 by cletinic         ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

int main (int argc, char **argv)
{
	int index;

	index = 0;
	if (argc == 2)
	{
		while (argv[1][index])
		{
			if ((argv[1][index] >= 'A' && argv[1][index] <= 'M') || (argv[1][index] >= 'a' && argv[1][index] <= 'm'))
				argv[1][index] += 13;
			else if ((argv[1][index] >= 'N' && argv[1][index] <= 'Z') || (argv[1][index] >= 'n' && argv[1][index] <= 'z'))
				argv[1][index] -=13;
			write(1, &argv[1][index], 1);
			index++;
		}
	}
		write(1, "\n", 1);
	return (0);
}
