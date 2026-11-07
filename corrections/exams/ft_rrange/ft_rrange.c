#include <stdlib.h>

int     *ft_rrange(int start, int end)
{
    int		*s;
    int		len = (end >= start) ? end - start + 1 : start - end + 1;
    if (!(s = (int*)malloc(sizeof(int) * len)))
        return (NULL);
    while (len--)
        s[len] = (end >= start) ? start++ : start--;
    return (s);
}
