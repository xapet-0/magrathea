/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_list_push_front.c                               :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/16 13:57:41 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/16 14:53:30 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_list.h"

void	ft_list_push_front(t_list **begin_list, void *data)
{
	t_list	*push;

	if (*begin_list)
	{
		push = ft_create_elem(data);
		push->next = *begin_list;
		*begin_list = push;
	}
	else
		*begin_list = ft_create_elem(data);
}
