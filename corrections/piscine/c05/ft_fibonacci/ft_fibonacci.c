/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   ft_fibonacci.c                                     :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: ybayart <marvin@42.fr>                     +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2019/08/05 17:08:09 by ybayart           #+#    #+#             */
/*   Updated: 2019/08/07 12:45:40 by ybayart          ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

int		ft_fibonacci_recur(int index, int n1, int n2)
{
	if (index == 0)
		return (0);
	if (index == 1)
		return (n2);
	if (index > 1)
		return (ft_fibonacci_recur(index - 1, n2, n1 + n2));
	return (-1);
}

int		ft_fibonacci(int index)
{
	return (ft_fibonacci_recur(index, 0, 1));
}
