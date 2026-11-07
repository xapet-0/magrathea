/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_is_sort.c                                       :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/15 11:56:48 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/22 11:16:59 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

int		ft_is_sort(int *tab, int lenght, int (*f)(int, int))
{
	int		i;
	int		haut;
	int		bas;

	i = 0;
	haut = 0;
	bas = 0;
	while (i < lenght - 1)
	{
		if ((*f)(tab[i], tab[i + 1]) >= 0)
			haut++;
		if ((*f)(tab[i], tab[i + 1]) <= 0)
			bas++;
		i++;
	}
	if (haut == i || bas == i)
		return (1);
	return (0);
}
