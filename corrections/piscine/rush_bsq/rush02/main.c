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

static const char	*g_units[20] = {"zero", "one", "two", "three", "four",
	"five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
	"thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
	"nineteen"};
static const char	*g_tens[10] = {"", "", "twenty", "thirty", "forty", "fifty",
	"sixty", "seventy", "eighty", "ninety"};

static void	put_s(const char *s)
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
	if (n < 20)
		put_s(g_units[n]);
	else
	{
		put_s(g_tens[n / 10]);
		if (n % 10)
		{
			put_s(" ");
			put_s(g_units[n % 10]);
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
