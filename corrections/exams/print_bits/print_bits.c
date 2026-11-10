/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   print_bits.c                                       :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: cletinic <marvin@42.fr>                    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/07/03 15:02:12 by cletinic          #+#    #+#             */
/*   Updated: 2018/07/03 15:17:47 by cletinic         ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

void	print_bits(unsigned char octet)
{
	int divide;
	int oct;

	oct = octet; 
	divide = 128; // 1 byte or 8 bits 
	while (divide)
	{
		if (divide <= oct)
		{
			write(1, "1", 1);
			oct %= divide;
		}
		else
			write(1, "0", 1);
		divide /= 2;
	}
}
