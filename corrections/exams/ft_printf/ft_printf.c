#include <unistd.h>
#include <stdarg.h>

static void	put_str(char *s, int *len)
{
	if (!s)
		s = "(null)";
	while (*s)
		*len += write(1, s++, 1);
}

static void	put_num(long long n, int base, int *len)
{
	char	*hex = "0123456789abcdef";

	if (n < 0)
	{
		*len += write(1, "-", 1);
		n = -n;
	}
	if (n >= base)
		put_num(n / base, base, len);
	*len += write(1, &hex[n % base], 1);
}

int	ft_printf(const char *fmt, ...)
{
	va_list	ap;
	int		len = 0;

	va_start(ap, fmt);
	while (*fmt)
	{
		if (*fmt == '%' && *(fmt + 1))
		{
			fmt++;
			if (*fmt == 's')
				put_str(va_arg(ap, char *), &len);
			else if (*fmt == 'd')
				put_num((long long)va_arg(ap, int), 10, &len);
			else if (*fmt == 'x')
				put_num((long long)va_arg(ap, unsigned int), 16, &len);
		}
		else
			len += write(1, fmt, 1);
		fmt++;
	}
	va_end(ap);
	return (len);
}
