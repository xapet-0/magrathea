#include <unistd.h>
void print_bits_rev(unsigned char octet)
{
	int i = 0;
	while (i < 8)
	{
		char c = ((octet >> i) & 1) + '0';
		write(1, &c, 1);
		i++;
	}
}
