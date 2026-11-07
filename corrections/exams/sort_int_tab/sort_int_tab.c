/* ************************************************************************** */
/*                                                                            */
/*                                                        :::      ::::::::   */
/*   sort_int_tab.c                                     :+:      :+:    :+:   */
/*                                                    +:+ +:+         +:+     */
/*   By: exam <marvin@42.fr>                        +#+  +:+       +#+        */
/*                                                +#+#+#+#+#+   +#+           */
/*   Created: 2018/07/25 10:45:36 by exam              #+#    #+#             */
/*   Updated: 2018/07/25 11:14:41 by exam             ###   ########.fr       */
/*                                                                            */
/* ************************************************************************** */

void	ft_swap(int *a, int *b)
{
	int temp;

	temp = *a;
	*a = *b;
	*b = temp;
}

void sort_int_tab(int *tab, unsigned int size)
{
	unsigned int index = 0;
	while (index + 1 <= size -1)
	{
		if (tab[index] == tab[index + 1])
			index++;
		else if (tab[index] > tab[index + 1])
		{
			ft_swap(&tab[index], &tab[index + 1]);
			index = 0;
		}
		else if (tab[index] < tab[index + 1])
			index++;
		else
			index++;
	}
}

/*
#include <stdio.h>
int main ()
{
	int a = 5;
	int b = 1;
	
	printf("\nswap\n");
	ft_swap(&a, &b);
	printf("a = %i, b = %i", a, b);

	printf("\ntab\n");
	int tab[] = {19, 18, 5, -1, 8, 0, 2, -20, +50, 0};
	int index = 0;
	int size = 10;
	while (index < size)
	{
		printf("|%i| ", tab[index++]);
	}
	printf("\nnew\n");
	index = 0;
	sort_int_tab(tab, size);
	while (index <= size - 1)
	{
		printf("|%i| ", tab[index++]);
	}
	return (0);
}
*/
