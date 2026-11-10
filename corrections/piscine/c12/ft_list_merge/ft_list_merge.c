/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_list_merge.c                                    :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/22 15:08:50 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 16:55:30 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_list.h"

void	ft_list_merge(t_list **begin_list, t_list *begin_list2)
{
	t_list	*list;

	if (begin_list == 0 || *begin_list == 0)
		*begin_list = begin_list2;
	else
	{
		list = *begin_list;
		while (list->next)
			list = list->next;
		list->next = begin_list2;
	}
}
