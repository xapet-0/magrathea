/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   vbc.c                                              :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: marvin <marvin@42.fr>                      +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/26 10:00:00 by marvin            #+#    #+#             */
/*   Updated: 2026/11/07 03:30:00 by marvin           ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>

static const char	*g_s;
static int			g_pos;
static int			g_err;

static long	parse_expr(void);

static void	report_error(void)
{
	if (g_err)
		return ;
	g_err = 1;
	if (g_s[g_pos] == '\0')
		printf("Unexpected end of input\n");
	else
		printf("Unexpected token '%c'\n", g_s[g_pos]);
}

static long	parse_factor(void)
{
	long	v;

	if (g_err)
		return (0);
	if (g_s[g_pos] == '(')
	{
		g_pos++;
		v = parse_expr();
		if (g_err)
			return (0);
		if (g_s[g_pos] != ')')
		{
			report_error();
			return (0);
		}
		g_pos++;
		return (v);
	}
	if (isdigit((unsigned char)g_s[g_pos]))
	{
		v = g_s[g_pos] - '0';
		g_pos++;
		if (isdigit((unsigned char)g_s[g_pos]))
		{
			report_error();
			return (0);
		}
		return (v);
	}
	report_error();
	return (0);
}

static long	parse_term(void)
{
	long	v;
	long	rhs;

	v = parse_factor();
	while (!g_err && g_s[g_pos] == '*')
	{
		g_pos++;
		rhs = parse_factor();
		v *= rhs;
	}
	return (v);
}

static long	parse_expr(void)
{
	long	v;
	long	rhs;

	v = parse_term();
	while (!g_err && g_s[g_pos] == '+')
	{
		g_pos++;
		rhs = parse_term();
		v += rhs;
	}
	return (v);
}

int	main(int argc, char **argv)
{
	long	res;

	if (argc != 2)
		return (1);
	g_s = argv[1];
	g_pos = 0;
	g_err = 0;
	res = parse_expr();
	if (!g_err && g_s[g_pos] != '\0')
		report_error();
	if (g_err)
		return (1);
	printf("%ld\n", res);
	return (0);
}
