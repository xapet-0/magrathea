/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   match_n_match.c                                    :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: deepthought <deepthought@student.42.fr>    +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/01/01 00:00:00 by deepthought       #+#    #+#             */
/*   Updated: 2026/01/01 00:00:00 by deepthought      ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

int	match(char *s1, char *s2)
{
	if (*s1 == '\0' && *s2 == '\0')
		return (1);
	if (*s2 == '*')
	{
		if (*s1 == '\0')
			return (match(s1, s2 + 1));
		return (match(s1 + 1, s2) || match(s1, s2 + 1));
	}
	if (*s1 == *s2)
		return (match(s1 + 1, s2 + 1));
	return (0);
}

int	nmatch(char *s1, char *s2)
{
	if (*s1 == '\0' && *s2 == '\0')
		return (1);
	if (*s2 == '*')
	{
		if (*s1 == '\0')
			return (nmatch(s1, s2 + 1));
		return (nmatch(s1 + 1, s2) + nmatch(s1, s2 + 1));
	}
	if (*s1 == *s2)
		return (nmatch(s1 + 1, s2 + 1));
	return (0);
}
