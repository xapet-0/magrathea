/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_list_remove_if.c                                :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/22 14:40:01 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 20:15:14 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include <stdlib.h>
#include "ft_list.h"

void	ft_list_remove_if(t_list **begin_list,
		void *data_ref, int (*cmp)(), void (*free_fct)(void *))
{
	t_list	*cur;
	t_list	*prev;
	t_list	*next;

	if (!begin_list || !*begin_list)
		return ;
	cur = *begin_list;
	prev = NULL;
	while (cur)
	{
		next = cur->next;
		if ((*cmp)(cur->data, data_ref) == 0)
		{
			if (prev)
				prev->next = next;
			else
				*begin_list = next;
			(*free_fct)(cur->data);
			free(cur);
		}
		else
			prev = cur;
		cur = next;
	}
}
