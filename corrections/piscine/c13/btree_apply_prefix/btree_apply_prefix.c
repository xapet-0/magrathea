/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   btree_apply_prefix.c                               :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/22 18:51:17 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 21:27:00 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_btree.h"

void	btree_apply_prefix(t_btree *root, void (*apply)(void *))
{
	if (!root)
		return ;
	(*apply)(root->item);
	if (root->left != 0)
		btree_apply_prefix(root->left, apply);
	if (root->right != 0)
		btree_apply_prefix(root->right, apply);
}
