/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_atoi_base.c                                     :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

static int	check_base(char *b)
{
	int	i;
	int	j;

	i = 0;
	while (b[i])
	{
		if (b[i] == '+' || b[i] == '-' || b[i] == ' '
			|| (b[i] >= 9 && b[i] <= 13))
			return (0);
		j = i + 1;
		while (b[j])
			if (b[i] == b[j++])
				return (0);
		i++;
	}
	if (i >= 2)
		return (i);
	return (0);
}

static int	base_idx(char c, char *b)
{
	int	i;

	i = 0;
	while (b[i])
	{
		if (b[i] == c)
			return (i);
		i++;
	}
	return (-1);
}

int	ft_atoi_base(char *str, char *base)
{
	int	blen;
	int	i;
	int	sign;
	long	res;

	blen = check_base(base);
	if (!blen)
		return (0);
	i = 0;
	sign = 1;
	res = 0;
	while (str[i] == ' ' || (str[i] >= 9 && str[i] <= 13))
		i++;
	while (str[i] == '+' || str[i] == '-')
		if (str[i++] == '-')
			sign = -sign;
	while (base_idx(str[i], base) >= 0)
	{
		res = res * blen + base_idx(str[i], base);
		i++;
	}
	return (res * sign);
}
