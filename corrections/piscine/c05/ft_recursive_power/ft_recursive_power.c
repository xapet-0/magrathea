/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_recursive_power.c                               :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/05 16:47:58 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/07 12:41:29 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

int		ft_recursive_power_recur(int nb, int power, int n)
{
	if (power == 0)
		return (1);
	if (power == 1)
		return (n);
	if (power >= 1)
		return (ft_recursive_power_recur(nb, power - 1, n * nb));
	return (0);
}

int		ft_recursive_power(int nb, int power)
{
	return (ft_recursive_power_recur(nb, power, nb));
}
