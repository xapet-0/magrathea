/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   main.c                                             :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <unistd.h>

static void	put_s(char *s)
{
	int	i;

	i = 0;
	while (s[i])
		i++;
	write(1, s, i);
}

static int	is_valid_uint(char *s)
{
	int	i;

	if (!s || !s[0])
		return (0);
	i = 0;
	while (s[i])
	{
		if (s[i] < '0' || s[i] > '9')
			return (0);
		i++;
	}
	return (1);
}

static void	say_under_100(long n)
{
	char	*u[20];
	char	*t[10];

	u[0] = "zero"; u[1] = "one"; u[2] = "two"; u[3] = "three";
	u[4] = "four"; u[5] = "five"; u[6] = "six"; u[7] = "seven";
	u[8] = "eight"; u[9] = "nine"; u[10] = "ten"; u[11] = "eleven";
	u[12] = "twelve"; u[13] = "thirteen"; u[14] = "fourteen";
	u[15] = "fifteen"; u[16] = "sixteen"; u[17] = "seventeen";
	u[18] = "eighteen"; u[19] = "nineteen";
	t[2] = "twenty"; t[3] = "thirty"; t[4] = "forty"; t[5] = "fifty";
	t[6] = "sixty"; t[7] = "seventy"; t[8] = "eighty"; t[9] = "ninety";
	if (n < 20)
		put_s(u[n]);
	else
	{
		put_s(t[n / 10]);
		if (n % 10)
		{
			put_s(" ");
			put_s(u[n % 10]);
		}
	}
}

static void	say_num(long n)
{
	if (n >= 1000)
	{
		say_num(n / 1000);
		put_s(" thousand");
		if (n % 1000)
		{
			put_s(" ");
			say_num(n % 1000);
		}
	}
	else if (n >= 100)
	{
		say_num(n / 100);
		put_s(" hundred");
		if (n % 100)
		{
			put_s(" ");
			say_num(n % 100);
		}
	}
	else
		say_under_100(n);
}

int	main(int argc, char **argv)
{
	char	*arg;
	long	n;
	int		i;

	if (argc < 2 || argc > 3)
	{
		put_s("Error\n");
		return (0);
	}
	arg = argv[argc - 1];
	if (!is_valid_uint(arg))
	{
		put_s("Error\n");
		return (0);
	}
	n = 0;
	i = 0;
	while (arg[i])
		n = n * 10 + (arg[i++] - '0');
	say_num(n);
	put_s("\n");
	return (0);
}
