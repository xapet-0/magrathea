unsigned int active_bits(int value)
{
	unsigned int u = (unsigned int)value, c = 0;
	while (u) { c += (u & 1); u >>= 1; }
	return (c);
}
