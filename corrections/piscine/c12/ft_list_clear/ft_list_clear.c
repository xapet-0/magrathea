/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_list_clear.c                                    :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/17 09:40:18 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 20:13:10 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

#include "ft_list.h"

void	ft_list_clear(t_list *begin_with, void (*free_fct)(void *))
{
	t_list	*ptr;

	if (begin_with)
		while (begin_with)
		{
			(*free_fct)(begin_with->data);
			ptr = begin_with->next;
			free(begin_with);
			begin_with = ptr;
		}
}
