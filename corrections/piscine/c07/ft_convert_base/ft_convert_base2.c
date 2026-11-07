/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_convert_base2.c                                 :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <stdlib.h>

int	ft_strlen(char *str)
{
	int	i;

	i = 0;
	while (str[i])
		i++;
	return (i);
}

int	ft_power(int n, int p)
{
	if (p < 0)
		return (0);
	if (p == 0)
		return (1);
	return (n * ft_power(n, p - 1));
}

static int	get_len(long nb, int blen, int is_neg)
{
	int	len;

	if (nb == 0)
		return (1);
	len = 0;
	if (is_neg < 0)
		len++;
	while (nb > 0)
	{
		nb /= blen;
		len++;
	}
	return (len);
}

char	*ft_putnbr_base(int nbr, char *base, int is_neg)
{
	long	nb;
	int		blen;
	int		len;
	char	*res;

	nb = nbr;
	blen = ft_strlen(base);
	len = get_len(nb, blen, is_neg);
	res = (char *)malloc(sizeof(char) * (len + 1));
	if (!res)
		return (0);
	res[len] = '\0';
	if (nb == 0)
		res[0] = base[0];
	else if (is_neg < 0)
		res[0] = '-';
	while (nb > 0)
	{
		res[--len] = base[nb % blen];
		nb /= blen;
	}
	return (res);
}
