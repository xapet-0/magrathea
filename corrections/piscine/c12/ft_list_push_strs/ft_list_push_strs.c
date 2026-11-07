/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_list_push_strs.c                                :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/16 16:17:18 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 20:12:59 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_list.h"

t_list	*ft_list_push_strs(int size, char **strs)
{
	t_list	*elem;
	t_list	*elem2;
	int		i;

	if (size <= 0)
		return (0);
	elem = ft_create_elem(strs[0]);
	i = 0;
	while (++i < size)
	{
		elem2 = ft_create_elem(strs[i]);
		elem2->next = elem;
		elem = elem2;
	}
	return (elem);
}
