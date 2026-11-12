/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   btree_apply_by_level.c                             :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/22 20:26:55 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 21:49:29 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_btree.h"

int	ft_max(int a, int b)
{
	if (a > b)
		return (a);
	return (b);
}

int	ft_btree_level_count(t_btree *root)
{
	int		count;

	count = 0;
	if (root == 0)
		return (0);
	if (root->left)
		count = ft_max(count, ft_btree_level_count(root->left));
	if (root->right)
		count = ft_max(count, ft_btree_level_count(root->right));
	return (count + 1);
}

void	apply_lvl(t_btree *root, int cur, int *info,
		void (*applyf)(void *item, int current_level, int is_first_elem))
{
	if (!root)
		return ;
	if (cur == info[0])
	{
		applyf(root->item, cur, info[1]);
		info[1] = 0;
		return ;
	}
	apply_lvl(root->left, cur + 1, info, applyf);
	apply_lvl(root->right, cur + 1, info, applyf);
}

void	btree_apply_by_level(t_btree *root,
		void (*applyf)(void *item, int current_level, int is_first_elem))
{
	int		count;
	int		info[2];

	if (!root)
		return ;
	count = ft_btree_level_count(root);
	info[0] = 0;
	while (info[0] < count)
	{
		info[1] = 1;
		apply_lvl(root, 0, info, applyf);
		info[0]++;
	}
}
