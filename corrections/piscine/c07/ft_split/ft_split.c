/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_split.c                                         :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <stdlib.h>

static int	is_sep(char c, char *charset)
{
	int	i;

	i = 0;
	while (charset[i])
		if (c == charset[i++])
			return (1);
	return (0);
}

static int	count_words(char *s, char *charset)
{
	int	c;
	int	i;

	c = 0;
	i = 0;
	while (s[i])
	{
		while (s[i] && is_sep(s[i], charset))
			i++;
		if (s[i])
			c++;
		while (s[i] && !is_sep(s[i], charset))
			i++;
	}
	return (c);
}

static char	*dup_word(char *s, int start, int len)
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

char	**ft_split(char *str, char *charset)
{
	char	**res;
	int		i;
	int		k;
	int		start;

	res = (char **)malloc(sizeof(char *) * (count_words(str, charset) + 1));
	if (!res)
		return (NULL);
	i = 0;
	k = 0;
	while (str[i])
	{
		while (str[i] && is_sep(str[i], charset))
			i++;
		if (!str[i])
			break ;
		start = i;
		while (str[i] && !is_sep(str[i], charset))
			i++;
		res[k++] = dup_word(str, start, i - start);
	}
	res[k] = NULL;
	return (res);
}
