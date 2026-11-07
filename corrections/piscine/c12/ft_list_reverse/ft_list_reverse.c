/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_list_reverse.c                                  :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/22 10:20:28 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 17:01:50 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_list.h"

void	ft_list_push(t_list **begin_list, t_list *elem)
{
	if (begin_list)
	{
		elem->next = *begin_list;
		*begin_list = elem;
	}
	else
		*begin_list = elem;
}

void	ft_list_reverse(t_list **begin_with)
{
	t_list	*reverse;
	t_list	*list;
	t_list	*next;

	reverse = 0;
	list = *begin_with;
	while (list)
	{
		next = list->next;
		ft_list_push(&reverse, list);
		list = next;
	}
	*begin_with = reverse;
}
