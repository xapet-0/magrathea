#include <unistd.h>

static int is_vow(char c)
{
	return (c=='a'||c=='e'||c=='i'||c=='o'||c=='u'||c=='A'||c=='E'||c=='I'||c=='O'||c=='U');
}

static void put_nbr(int n)
{
	char c;
	if (n >= 10) put_nbr(n / 10);
	c = (n % 10) + '0';
	write(1, &c, 1);
}

int main(int ac, char **av)
{
	if (ac != 2) { write(1, "\n", 1); return 0; }
	char *s = av[1];
	int len = 0, vowels = 0;
	while (s[len]) { if (is_vow(s[len])) vowels++; len++; }
	write(1, "Reversed: ", 10);
	int end = len;
	int first = 1;
	while (end > 0)
	{
		while (end > 0 && (s[end - 1] == '_' || s[end - 1] == ' ')) end--;
		int start = end;
		while (start > 0 && s[start - 1] != '_' && s[start - 1] != ' ') start--;
		if (start < end)
		{
			if (!first) write(1, " ", 1);
			write(1, s + start, end - start);
			first = 0;
		}
		end = start;
	}
	write(1, "\nVowel count: ", 14);
	put_nbr(vowels);
	write(1, "\n", 1);
	return 0;
}
