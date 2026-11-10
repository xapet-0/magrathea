/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   reverse_bits.c                                     :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: exam <marvin@42.fr>                        +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/07/11 10:03:15 by exam              #+#    #+#             */
/*   Updated: 2018/07/11 10:42:00 by exam             ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

unsigned char	reverse_bits(unsigned char octet)
{ 
	return ((((octet >> 0) & 1) << 7) |
			(((octet >> 1) & 1) << 6) |
			(((octet >> 2) & 1) << 5) |
			(((octet >> 3) & 1) << 4) |
			(((octet >> 4) & 1) << 3) |
			(((octet >> 5) & 1) << 2) |
			(((octet >> 6) & 1) << 1) |
			(((octet >> 7) & 1) << 0));
}

/*
#include <unistd.h>
unsigned char print_bits (unsigned char octet)
{
	int i = 128;
	while (i)
	{
		if (octet / i)
		{
			write(1, "1", 1);
			octet -= i;
		}
		else if (!(octet / i))
		{
			write(1, "0", 1);
		}
		i = i / 2;
	}
	return (octet);
}

#include <stdio.h>
int main ()
{	int n = 130;
	char octet = reverse_bits(n);
	print_bits(n);
	//print_bits(128);
   printf("\n");	
	//printf("%c", reverse_bits(1));
	//printf("\n");
   	print_bits(octet);	
	return (0);
}
*/
