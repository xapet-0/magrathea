static int	char_val(char c)
{
	if (c >= '0' && c <= '9')
		return (c - '0');
	if (c >= 'a' && c <= 'z')
		return (c - 'a' + 10);
	if (c >= 'A' && c <= 'Z')
		return (c - 'A' + 10);
	return (-1);
}

int	parse_int_base(const char *str, int base)
{
	int	i;
	int	sign;
	int	res;
	int	v;

	if (!str || base < 2 || base > 16)
		return (0);
	i = 0;
	sign = 1;
	res = 0;
	while (str[i] == ' ' || (str[i] >= 9 && str[i] <= 13))
		i++;
	if (str[i] == '-' || str[i] == '+')
	{
		if (str[i] == '-')
			sign = -1;
		i++;
	}
	while (str[i])
	{
		v = char_val(str[i]);
		if (v < 0 || v >= base)
			break ;
		res = res * base + v;
		i++;
	}
	return (res * sign);
}
