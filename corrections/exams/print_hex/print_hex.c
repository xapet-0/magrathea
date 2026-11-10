/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   print_hex.c                                        :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: cletinic <marvin@42.fr>                    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/08/01 07:49:26 by cletinic          #+#    #+#             */
/*   Updated: 2018/08/01 08:54:06 by cletinic         ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

void	print_hex(int n)
{
	if (n >= 16)
		print_hex(n /16);
	if (n % 16 < 10)
		n = (n % 16) + '0'; // it it is a digit - get the ascii of dthe digit
	else 
		n = (n % 16) - 10 + 'a'; // if number is hex (a - f (10 - 16))
	write(1, &n, 1);
}

int			ft_atoi(char *s)
{
	int index = 0;
	int result = 0;

	if (s[index] == ' ' || (s[index] >= '\t' && s[index] <= '\r'))
		index++;
	if (s[index] == '+' || s[index] == '-')
	{
		if (s[index] == '-')
			return (-1);
		index++;
	}
	while (s[index])
		result = s[index++] - '0' + (result * 10);
	return (result);
}

int main (int argc, char **argv)
{
	if (argc == 2)
	{
		int av = ft_atoi(argv[1]);
		if (av == -1)
		{
			write(1, "\n", 1);
			return (0);
		}
		else 
			print_hex(av);

	}
	write(1, "\n", 1);
	return (0);
}
