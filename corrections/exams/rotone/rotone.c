/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   rotone.c                                           :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: cletinic <marvin@42.fr>                    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/07/03 13:20:29 by cletinic          #+#    #+#             */
/*   Updated: 2018/07/03 13:39:32 by cletinic         ###   ########.fr       */
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
			if ((argv[1][index] >= 'A' && argv[1][index] <= 'Y') || (argv[1][index] >= 'a' && argv[1][index] <= 'y'))
				argv[1][index] += 1;
			else if (argv[1][index] == 'z' || argv[1][index] == 'Z')
				argv[1][index] -= 25;
			write(1, &argv[1][index], 1);
			index++;
		}
	}
	write(1, "\n", 1);
	return (0);
}
