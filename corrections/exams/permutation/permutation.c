/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   permutation.c                                      :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: marvin <marvin@42.fr>                      +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2026/10/26 10:00:00 by marvin            #+#    #+#             */
/*   Updated: 2026/11/07 03:30:00 by marvin           ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <stdlib.h>
#include <unistd.h>

static void	gen_perm(char *s, int n, char *cur, int *used, int depth)
{
	int	i;

	if (depth == n)
	{
		write(1, cur, n);
		write(1, "\n", 1);
		return ;
	}
	i = 0;
	while (i < n)
	{
		if (!used[i])
		{
			used[i] = 1;
			cur[depth] = s[i];
			gen_perm(s, n, cur, used, depth + 1);
			used[i] = 0;
		}
		i++;
	}
}

int	main(int argc, char **argv)
{
	char	*s;
	char	*cur;
	int		*used;
	int		n;
	int		i;
	int		j;
	char	tmp;

	if (argc != 2)
	{
		write(1, "\n", 1);
		return (0);
	}
	s = argv[1];
	n = 0;
	while (s[n])
		n++;
	i = 0;
	while (i < n)
	{
		j = i + 1;
		while (j < n)
		{
			if (s[i] > s[j])
			{
				tmp = s[i];
				s[i] = s[j];
				s[j] = tmp;
			}
			j++;
		}
		i++;
	}
	cur = (char *)malloc((size_t)n + 1);
	used = (int *)calloc((size_t)(n > 0 ? n : 1), sizeof(int));
	if (!cur || !used)
	{
		free(cur);
		free(used);
		return (1);
	}
	gen_perm(s, n, cur, used, 0);
	free(cur);
	free(used);
	return (0);
}
