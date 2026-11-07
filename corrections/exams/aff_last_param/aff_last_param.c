/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   aff_last_param.c                                   :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: cletinic <marvin@42.fr>                    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/06/25 07:09:32 by cletinic          #+#    #+#             */
/*   Updated: 2018/06/25 07:13:05 by cletinic         ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

int main (int argc, char **argv)
{
	int index;

	index = 0;
	if (argc == 1)
		write(1, "\n", 1);
	else if (argc >= 2)
	{
		while (argv[argc -1][index])
			write(1, &argv[argc -1][index++], 1);
		write(1, "\n", 1);
	}
	return (0);
}
