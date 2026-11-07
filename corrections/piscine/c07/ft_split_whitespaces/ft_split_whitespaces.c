/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_split_whitespaces.c                             :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <stdlib.h>

static int	is_ws(char c)
{
	return (c == ' ' || c == '\t' || c == '\n');
}

static int	count_w(char *s)
{
	int	c;
	int	i;

	c = 0;
	i = 0;
	while (s[i])
	{
		while (s[i] && is_ws(s[i]))
			i++;
		if (s[i])
			c++;
		while (s[i] && !is_ws(s[i]))
			i++;
	}
	return (c);
}

static char	*dup_w(char *s, int start, int len)
{
	char	*w;
	int		j;

	w = (char *)malloc(len + 1);
	if (!w)
		return (NULL);
	j = 0;
	while (j < len)
	{
		w[j] = s[start + j];
		j++;
	}
	w[len] = '\0';
	return (w);
}

char	**ft_split_whitespaces(char *str)
{
	char	**res;
	int		i;
	int		k;
	int		start;

	res = (char **)malloc(sizeof(char *) * (count_w(str) + 1));
	if (!res)
		return (NULL);
	i = 0;
	k = 0;
	while (str[i])
	{
		while (str[i] && is_ws(str[i]))
			i++;
		if (!str[i])
			break ;
		start = i;
		while (str[i] && !is_ws(str[i]))
			i++;
		res[k++] = dup_w(str, start, i - start);
	}
	res[k] = NULL;
	return (res);
}
