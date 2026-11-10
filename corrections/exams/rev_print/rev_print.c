/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   rev_print.c                                        :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: cletinic <marvin@42.fr>                    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/07/02 13:38:07 by cletinic          #+#    #+#             */
/*   Updated: 2018/07/02 13:50:07 by cletinic         ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

int main (int argc, char **argv)
{
	int length;

	length = 0;
	if (argc == 2)
	{
		while (argv[1][length])
			length++;
		length -= 1;
		while (length >= 0)
			write(1, &argv[1][length--], 1);
	}
	write (1, "\n", 1);
	return (0);
}
