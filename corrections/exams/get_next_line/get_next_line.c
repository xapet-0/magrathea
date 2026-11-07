#include <unistd.h>
#include <stdlib.h>

char	*get_next_line(int fd)
{
	char	*s = malloc(100000);
	char	c;
	int		i = 0;
	int		r;

	if (!s || fd < 0)
		return (free(s), NULL);
	while ((r = read(fd, &c, 1)) > 0)
	{
		s[i++] = c;
		if (c == '\n')
			break ;
	}
	if (r < 0 || i == 0)
		return (free(s), NULL);
	s[i] = '\0';
	return (s);
}
