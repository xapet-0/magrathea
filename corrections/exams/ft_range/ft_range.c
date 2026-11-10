#include <stdlib.h>

int		*ft_range(int min, int max)
{
	int		*res;
	int		size;
	int		step;
	int		i;

	size = (max >= min) ? (max - min + 1) : (min - max + 1);
	res = (int *)malloc(sizeof(int) * size);
	if (!res)
		return (NULL);
	step = (max >= min) ? 1 : -1;
	for (i = 0; i < size; i++)
	{
		res[i] = min;
		min += step;
	}
	return (res);
}
