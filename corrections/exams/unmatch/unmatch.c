int unmatch(int *tab, int length)
{
	int i = 0, x = 0;
	while (i < length) x ^= tab[i++];
	return (x);
}
