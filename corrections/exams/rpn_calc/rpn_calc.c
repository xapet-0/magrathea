#include "rpn_calc.h"

int	ft_is_num(char *str)
{
	int	i = 0;
	if (str[i] == '+' || str[i] == '-')
		i++;
	if (str[i] >= '0' && str[i] <= '9')
		return (1);
	return (0);
}

int	ft_is_op(char c)
{
    	if (c == '+' || c == '-' || c == '*' || c == '/' || c == '%')
        	return (1);
    	return (0);
}

void	ft_lst_add(t_list **begin_list, int val)
{
	t_list	*add;
	if ((add = (t_list *)malloc(sizeof(t_list))))
	{
		add->val = val;
		add->next = *begin_list;
		*begin_list = add;
	}
}

void 	ft_lst_del(t_list **begin_list)
{
    	t_list	*del;
    	del = *begin_list;
    	*begin_list = del->next;
    	free(del);
}

char 	*move(char *str)
{
	while (*str && *str != ' ')
		str++;
	return (str);
}

int	ft_calc(t_list **begin_list, char c)
{
	t_list	*start;
	int	*a;
	int	b;
	if (!(*begin_list) || !(start = (*begin_list)->next))
		return (0);
	a = &start->val;
	b = (*begin_list)->val;
	if (c == '+')
		*a += b;
	else if (c == '-')
		*a -= b;
	else if (c == '*')
		*a *= b;
	else if (c == '/')
	{
		if (b == 0)
			return (0);
		*a /= b;
	}
	else if (c == '%')
	{
		if (b == 0)
			return (0);
		*a %= b;
	}
	ft_lst_del(begin_list);
	return (1);
}

int		main(int ac, char **av)
{
	if (ac == 2)
	{
		char	*str = av[1];
		t_list	*begin_list = NULL;
		while (*str)
		{
			if (ft_is_num(str))
			{
				ft_lst_add(&begin_list, atoi(str));
				str = move(str);
			}
			else if (ft_is_op(*str))
			{
				if (!ft_calc(&begin_list, *str))
					break;
				str = move(str);
			}
			else if (*str == ' ')
			{
				if (!*(str + 1))
					break;
				str++;
			}
			else
				break;
		}
		if (*str || begin_list->next)
			write(1, "Error\n", 6);
		else
			printf("%d\n", begin_list->val);
		while (begin_list)
			ft_lst_del(&begin_list);
	}
	else
		write(1, "Error\n", 6);
}
