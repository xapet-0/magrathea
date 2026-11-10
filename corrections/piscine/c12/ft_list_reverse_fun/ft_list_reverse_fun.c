/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_list_reverse_fun.c                              :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/22 15:59:07 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 20:17:04 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_list.h"

void	ft_list_reverse_fun(t_list *begin_list)
{
	int		n;
	int		i;
	int		j;
	t_list	*list;
	void	*tmp;

	n = 0;
	list = begin_list;
	while (list && ++n)
		list = list->next;
	i = 0;
	while (i < n - 1)
	{
		j = i;
		list = begin_list;
		while (list && list->next && j < n - 1)
		{
			tmp = list->data;
			list->data = list->next->data;
			list->next->data = tmp;
			list = list->next;
			j++;
		}
		i++;
	}
}
