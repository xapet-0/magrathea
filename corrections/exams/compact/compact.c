int compact(char **tab, int length)
{
	int i = 0, j = 0;
	while (i < length) { if (tab[i]) tab[j++] = tab[i]; i++; }
	return (j);
}
