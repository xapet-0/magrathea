/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   btree_insert_data.c                                :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/22 19:08:34 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 21:28:35 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_btree.h"

void	btree_insert_data(t_btree **root, void *item,
		int (*cmpf)(void *, void *))
{
	t_btree	*btree;

	if (root == 0 || *root == 0 || item == 0)
	{
		if (item && root)
			*root = btree_create_node(item);
		return ;
	}
	btree = *root;
	if ((*cmpf)(item, (*root)->item) < 0)
	{
		if (btree->left)
			btree_insert_data(&btree->left, item, cmpf);
		else
			btree->left = btree_create_node(item);
	}
	else
	{
		if (btree->right)
			btree_insert_data(&btree->right, item, cmpf);
		else
			btree->right = btree_create_node(item);
	}
}
