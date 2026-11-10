#include <unistd.h>

char	g_bytarr[2048];
char	*g_ptr;
char	*g_arg;

void	issqr()
{
	int br;

	br = 0;
	if (*g_arg == '[')
	{
		while (*g_arg)
		{
			if (*g_arg == '[')
				br++;
			else if (*g_arg == ']')
				br--;
			if (br == 0)
				return;
			g_arg++;
		}
	}
	else
	{
		while (*g_arg)
		{
			if (*g_arg == ']')
				br++;
			else if (*g_arg == '[')
				br--;
			if (br == 0)
				return;
			g_arg--;
		}
	}
}

int		main(int argc, char **argv)
{
	if (argc == 2)
	{
		g_arg = argv[1];
		g_ptr = g_bytarr;
		while (*g_arg )
		{
			if (*g_arg == '>')
				g_ptr++;
			else if (*g_arg == '<')
				g_ptr--;
			else if (*g_arg == '+')
				(*g_ptr)++;
			else if (*g_arg == '-')
				(*g_ptr)--;
			else if (*g_arg == '.')
				write(1, g_ptr, 1);
			else if (*g_arg == '[')
			{
				if (*g_ptr == 0)
					issqr();
			}
			else if (*g_arg == ']')
			{
				if (*g_ptr != 0)
					issqr();
			}
			g_arg++;
		}		
	}
	else
		write(1, "\n", 1);
	return (0);
}
