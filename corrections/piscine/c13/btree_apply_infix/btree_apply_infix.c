/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   btree_apply_infix.c                                :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/22 18:58:38 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 21:27:23 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_btree.h"

void	btree_apply_infix(t_btree *root, void (*applyf)(void *))
{
	if (!root)
		return ;
	if (root->left != 0)
		btree_apply_infix(root->left, applyf);
	(*applyf)(root->item);
	if (root->right != 0)
		btree_apply_infix(root->right, applyf);
}
