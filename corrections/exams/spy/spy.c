#include <unistd.h>
static int match_w(const char *s, const char *w)
{
	while (*s == ' ' || *s == '\t') s++;
	while (*w)
	{
		char c = (*s >= 'A' && *s <= 'Z') ? *s + 32 : *s;
		if (c != *w) return (0);
		s++; w++;
	}
	while (*s == ' ' || *s == '\t') s++;
	return (*s == '\0');
}
int main(int ac, char **av)
{
	int i = 1;
	while (i < ac)
	{
		if (match_w(av[i], "president") || match_w(av[i], "attack") || match_w(av[i], "powers"))
		{
			write(1, "Alert!!!\n", 9);
			return (0);
		}
		i++;
	}
	return (0);
}
